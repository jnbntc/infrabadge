#!/usr/bin/env python3
"""Opt-in temporary HTTPS observation front end for an unchanged M3 gateway.

The installed collector/gateway continue on localhost. This lab front end relays
only one authenticated device GET, verifies upstream TLS and records closed enums
without payloads/headers/addresses. No USB, firmware writes or network settings.
"""

import argparse
import asyncio
import hashlib
import ipaddress
import json
import os
import re
import ssl
import sys
import tempfile
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gateway"), str(ROOT / "collector/fedora")]
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from infrabadge_collector.runtime import private_bytes, require_host
from infrabadge_gateway.app import authenticate, bounded_json
from infrabadge_gateway.models import GatewayConfig, Snapshot

TAG = re.compile(r'"[0-9a-f]{64}"')
OUTCOMES = {"completed", "authentication_rejected", "upstream_unavailable", "upstream_invalid"}


class Evidence:
    """Bounded private journal. Values come from validated enums, never clients."""

    def __init__(self, output=None, capacity=64, clock=time.time):
        if type(capacity) is not int or not 1 <= capacity <= 128:
            raise ValueError("journal_capacity")
        self.events = deque(maxlen=capacity)
        self.sequence = 0
        self.output = Path(output) if output else None
        self.clock = clock
        if self.output:
            parent = self.output.parent
            if (
                self.output.exists()
                or self.output.is_symlink()
                or not parent.is_dir()
                or parent.is_symlink()
                or parent.stat().st_uid != os.getuid()
                or parent.stat().st_mode & 0o077
            ):
                raise ValueError("new_private_journal_required")

    def record(self, outcome, code, conditional, state=None, control=None):
        if (
            outcome not in OUTCOMES
            or type(code) is not int
            or code not in (200, 304, 401, 502, 504)
            or type(conditional) is not bool
            or state not in (None, "HEALTHY", "WARNING", "CRITICAL", "UNKNOWN", "OFFLINE")
            or control not in (None, "fresh", "stale", "absent")
        ):
            raise ValueError("invalid_observation")
        self.sequence += 1
        self.events.append(
            dict(
                sequence=self.sequence,
                received_at=int(self.clock()),
                outcome=outcome,
                http_status=code,
                conditional=conditional,
                state=state,
                control=control,
            )
        )
        if self.output:
            fd, temporary = tempfile.mkstemp(prefix=".observation-", dir=self.output.parent)
            try:
                with os.fdopen(fd, "w") as stream:
                    json.dump(dict(events=list(self.events)), stream, allow_nan=False)
                os.replace(temporary, self.output)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)


def create_observer(device_id, identity, backend, evidence):
    """No arbitrary upstream, collector ingress, body or header forwarding."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", device_id):
        raise ValueError("logical_device")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    path = "/api/v1/devices/" + device_id + "/status"

    @app.get(path)
    async def observe(request: Request):
        authorizations = request.headers.getlist("authorization")
        conditional_headers = request.headers.getlist("if-none-match")
        conditional = bool(conditional_headers)
        try:
            if len(authorizations) != 1:
                raise HTTPException(401, "authentication rejected")
            # Existing constant-time, identity-scoped gateway authentication.
            authenticate(authorizations[0], identity)
        except HTTPException:
            evidence.record("authentication_rejected", 401, conditional)
            raise HTTPException(401, "authentication rejected") from None
        if (
            request.url.query
            or len(conditional_headers) > 1
            or (conditional_headers and not TAG.fullmatch(conditional_headers[0]))
            or request.headers.get("transfer-encoding")
            or request.headers.get("content-length", "0") != "0"
        ):
            raise HTTPException(400, "request rejected")
        headers = {"Authorization": authorizations[0], "Accept": "application/json"}
        if conditional_headers:
            headers["If-None-Match"] = conditional_headers[0]
        try:
            # A total deadline supplements HTTPX per-I/O timeouts. No redirects
            # or environment proxies; no caller-provided URL or arbitrary headers.
            async with asyncio.timeout(8):
                async with backend.stream("GET", path, headers=headers) as upstream:
                    code = upstream.status_code
                    if code not in (200, 304):
                        raise ValueError("unexpected_upstream_status")
                    tag = upstream.headers.get("etag", "")
                    now = upstream.headers.get("x-infrabadge-now", "")
                    if not TAG.fullmatch(tag) or not re.fullmatch(r"[0-9]{10}", now):
                        raise ValueError("upstream_headers")
                    if not 1577836800 <= int(now) <= 4102444800:
                        raise ValueError("upstream_clock")
                    data = bytearray()
                    async for chunk in upstream.aiter_bytes():
                        if len(data) + len(chunk) > 2048:
                            raise ValueError("upstream_size")
                        data.extend(chunk)
                    state = control = None
                    if code == 304:
                        if data or not conditional_headers or tag != conditional_headers[0]:
                            raise ValueError("upstream_304")
                    else:
                        if (
                            upstream.headers.get("content-type", "").split(";")[0]
                            != "application/json"
                        ):
                            raise ValueError("upstream_media_type")
                        snapshot = Snapshot.model_validate(bounded_json(data))
                        if snapshot.device_id != device_id or snapshot.simulated:
                            raise ValueError("upstream_identity_source")
                        if not snapshot.generated_at <= int(now) < snapshot.expires_at:
                            raise ValueError("upstream_freshness")
                        if '"' + hashlib.sha256(data).hexdigest() + '"' != tag:
                            raise ValueError("upstream_etag")
                        state, control = snapshot.status, "fresh"
                        details = {a.detail for a in snapshot.alerts}
                        if "DATOS CADUCADOS" in details:
                            control = "stale"
                        elif "SIN MUESTRA" in details:
                            control = "absent"
                    forwarded = {
                        "ETag": tag,
                        "X-InfraBadge-Now": now,
                        "Cache-Control": "private, no-cache",
                    }
                    evidence.record("completed", code, conditional, state, control)
                    return Response(
                        bytes(data),
                        status_code=code,
                        headers=forwarded,
                        media_type="application/json" if code == 200 else None,
                    )
        except (httpx.TransportError, TimeoutError):
            evidence.record("upstream_unavailable", 504, conditional)
            raise HTTPException(504, "gateway unavailable") from None
        except (ValueError, UnicodeError, RecursionError):
            evidence.record("upstream_invalid", 502, conditional)
            raise HTTPException(502, "gateway response rejected") from None

    return app


def selected_address(value):
    address = ipaddress.ip_address(value)
    if (
        address.version != 4
        or not address.is_private
        or address.is_loopback
        or address.is_unspecified
        or address.is_link_local
        or address.is_multicast
    ):
        raise ValueError("selected_private_lan_required")
    return address


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--authorized-temporary-observer", action="store_true")
    args = parser.parse_args()
    require_host()
    os.umask(0o077)
    # Bind address/destination/TLS paths are locally reviewed, private inputs.
    value = json.loads(private_bytes(args.private / "observer.json", 8192))
    if not args.authorized_temporary_observer:
        print("Preview only: temporary device GET observer; no USB or network changes.")
        return 0
    address = selected_address(value["listen_address"])
    config = GatewayConfig.model_validate_json(private_bytes(Path(value["gateway_config"]), 65536))
    identity = config.devices[value["device_id"]]
    if identity.node_id is None:
        raise ValueError("real_node_required")
    private_bytes(Path(value["server_key"]), 16384)
    context = ssl.create_default_context(cafile=value["ca_file"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    backend = httpx.AsyncClient(
        base_url="https://localhost:8443",
        verify=context,
        trust_env=False,
        follow_redirects=False,
        timeout=5,
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
    )
    evidence = Evidence(args.private / "observations.json")
    app = create_observer(value["device_id"], identity, backend, evidence)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=str(address),
            port=8443,
            ssl_certfile=value["server_cert"],
            ssl_keyfile=value["server_key"],
            access_log=False,
            log_level="critical",
            limit_concurrency=8,
            timeout_keep_alive=2,
            timeout_graceful_shutdown=5,
        )
    )
    asyncio.run(serve_bounded(server, backend))
    return 0


async def serve_bounded(server, backend, seconds=1200):
    task = asyncio.create_task(server.serve())
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=seconds)
    except TimeoutError:
        pass
    finally:
        server.should_exit = True
        try:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=10)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        finally:
            await backend.aclose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(
            "Observer stopped; inspect private inputs/results. No board accessed."
        ) from None
