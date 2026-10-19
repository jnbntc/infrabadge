#!/usr/bin/env python3
"""Real installed gateway -> temporary loopback HTTPS observer, without USB/LAN."""

import argparse
import asyncio
import hashlib
import json
import os
import socket
import ssl
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gateway"), str(ROOT / "collector/fedora")]
import httpx
import uvicorn
from infrabadge_collector.runtime import private_bytes, require_host
from infrabadge_gateway.models import Device, Snapshot
from observe_gateway import Evidence, create_observer


def certificate_rejection(error):
    pending, seen = [error], set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if isinstance(item, ssl.SSLCertVerificationError):
            return True
        if isinstance(item, BaseException):
            pending.extend(
                v
                for v in (item.__cause__, item.__context__, *item.args)
                if isinstance(v, BaseException)
            )
    return False


def check(private):
    require_host()
    os.umask(0o077)
    config = json.loads(private_bytes(private / "observer.json", 8192))
    client_config = json.loads(private_bytes(private / "client.json", 4096))
    device_id, token = client_config["device_id"], client_config["token"]
    identity = Device(
        node_id="workstation", token_sha256=[hashlib.sha256(token.encode()).hexdigest()]
    )
    context = ssl.create_default_context(cafile=config["ca_file"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    backend = httpx.AsyncClient(
        base_url="https://localhost:8443",
        verify=context,
        trust_env=False,
        follow_redirects=False,
        timeout=5,
    )
    evidence = Evidence(private / "loopback-observations.json")
    app = create_observer(device_id, identity, backend, evidence)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            ssl_certfile=config["server_cert"],
            ssl_keyfile=config["server_key"],
            access_log=False,
            log_level="critical",
            timeout_graceful_shutdown=3,
        )
    )

    async def serve():
        try:
            await server.serve(sockets=[listener])
        finally:
            await backend.aclose()

    thread = threading.Thread(target=lambda: asyncio.run(serve()), daemon=True)
    thread.start()
    try:
        end = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < end:
            time.sleep(0.01)
        if not server.started:
            raise ValueError("loopback_observer_not_ready")
        url = (
            "https://localhost:"
            + str(listener.getsockname()[1])
            + "/api/v1/devices/"
            + device_id
            + "/status"
        )
        with httpx.Client(
            verify=context, trust_env=False, follow_redirects=False, timeout=8
        ) as client:
            headers = {"Authorization": "Bearer " + token}
            reply = client.get(url, headers=headers)
            if reply.status_code != 200:
                raise ValueError("loopback_query_failed")
            snapshot = Snapshot.model_validate(reply.json())
            if snapshot.simulated or any(
                a.detail in ("SIN MUESTRA", "DATOS CADUCADOS") for a in snapshot.alerts
            ):
                raise ValueError("real_fresh_sample_required")
            same = client.get(url, headers={**headers, "If-None-Match": reply.headers["etag"]})
            if same.status_code != 304:
                # A legitimate scheduled sample may race the first conditional GET.
                same = client.get(url, headers={**headers, "If-None-Match": same.headers["etag"]})
            if same.status_code != 304 or same.content:
                raise ValueError("conditional_semantics_failed")
            if client.get(url, headers={"Authorization": "Bearer " + "x" * 40}).status_code != 401:
                raise ValueError("authentication_failed")
        try:
            with httpx.Client(trust_env=False, timeout=3) as unknown_ca:
                unknown_ca.get(url, headers={"Authorization": "Bearer " + token})
        except httpx.ConnectError as error:
            if not certificate_rejection(error):
                raise ValueError("unknown_ca_test_failed_for_non_tls_reason") from None
        else:
            raise ValueError("unknown_ca_not_rejected")
        return dict(
            status="passed",
            scope="installed_gateway_to_ephemeral_loopback_observer",
            fresh_real_snapshot=True,
            verified_tls_both_hops=True,
            etag_304=True,
            auth_401=True,
            unknown_ca_rejected=True,
            board_accessed=False,
            selected_lan_bound=False,
            installed_services_changed=False,
            exact_wake_cause_verified=False,
            electrical_measurements="DEFERRED",
        )
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("loopback_cleanup_failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", required=True, type=Path)
    args = parser.parse_args()
    result = check(args.private)
    from prepare_observer import write_private

    write_private(args.private / "loopback-result.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Observer check stopped; no board/LAN access. Inspect private results."
        ) from None
