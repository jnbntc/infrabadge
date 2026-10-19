import asyncio
import hashlib
import hmac
import json
import threading
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Path, Query, Request, Response
from pydantic import ValidationError

from .metrics import Evaluation, Metrics
from .models import Alert, Counts, GatewayConfig, Snapshot


def authenticate(authorization, identity):
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    digest = hashlib.sha256(token.encode()).hexdigest()
    accepted = False
    for value in identity.token_sha256 if identity else ["0" * 64]:
        accepted |= hmac.compare_digest(digest, value)
    if not identity or not 32 <= len(token) <= 96 or not accepted:
        raise HTTPException(401, "authentication rejected", headers={"WWW-Authenticate": "Bearer"})


def bounded_json(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("nonfinite value")

    return json.loads(body, object_pairs_hook=unique, parse_constant=invalid)


def fixture(
    device_id: str, state: str, now: int, revision: int, ttl_seconds: int = 1800
) -> Snapshot:
    counts = {"healthy": 12, "warning": 0, "critical": 0, "unknown": 0}
    alerts = []
    if state == "WARNING":
        counts.update(healthy=11, warning=1)
        alerts = [Alert(title="CPU ALTA", detail="NODO-02 / CPU 84%")]
    elif state == "CRITICAL":
        counts.update(healthy=10, critical=2)
        alerts = [
            Alert(title="SERVICIO CAIDO", detail="NODO-03 / API"),
            Alert(title="DISCO LLENO", detail="NODO-07 / USO 99%"),
        ]
    elif state in ("OFFLINE", "UNKNOWN"):
        counts.update(healthy=0, unknown=12)
        alerts = [Alert(title="SIN DATOS", detail="ESTADO DESCONOCIDO")]
    return Snapshot(
        schema_version=1,
        device_id=device_id,
        revision=revision,
        simulated=True,
        generated_at=now,
        expires_at=now + ttl_seconds,
        status=state,
        counts=Counts(**counts),
        alerts=alerts,
    )


def create_app(
    config: GatewayConfig, clock: Callable[[], float] = time.time, snapshot_ttl_seconds: int = 1800
) -> FastAPI:
    if type(snapshot_ttl_seconds) is not int or not 0 < snapshot_ttl_seconds <= 3600:
        raise ValueError("snapshot TTL outside protocol bounds")
    app = FastAPI(title="InfraBadge gateway", docs_url=None, redoc_url=None, openapi_url=None)
    lock = threading.Lock()
    cached: dict[str, Snapshot] = {}
    nodes = {key: Evaluation() for key in config.collectors}

    @app.post("/api/v1/collectors/{node_id}/metrics", status_code=202)
    async def ingest(
        node_id: str, request: Request, authorization: Annotated[str | None, Header()] = None
    ):
        collector = config.collectors.get(node_id)
        authenticate(authorization, collector)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "JSON required")
        if request.headers.get("content-encoding", "identity") != "identity":
            raise HTTPException(415, "content encoding rejected")
        body = bytearray()
        try:
            async with asyncio.timeout(10):
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 8192:
                        raise HTTPException(413, "payload too large")
                    body.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "body deadline exceeded") from None
        try:
            sample = Metrics.model_validate(bounded_json(body))
        except (ValueError, ValidationError, RecursionError, UnicodeError):
            raise HTTPException(422, "metrics rejected") from None
        now = int(clock())
        if (
            sample.node_id != node_id
            or not 0 <= now - sample.collected_at < collector.policy.sample_ttl_seconds
        ):
            raise HTTPException(422, "metrics identity or freshness rejected")
        with lock:
            evaluation = nodes[node_id]
            if evaluation.last and sample.collected_at <= evaluation.last.collected_at:
                raise HTTPException(409, "sample already superseded")
            if (
                evaluation.last
                and sample.collected_at - evaluation.last.collected_at
                < collector.policy.min_interval_seconds
            ):
                raise HTTPException(429, "sample interval too short")
            evaluation.ingest(sample, collector.policy)
        return {"accepted": True}

    @app.get("/api/v1/devices/{device_id}/status")
    def status(
        device_id: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$")],
        authorization: Annotated[str | None, Header()] = None,
        if_none_match: Annotated[str | None, Header()] = None,
        fault: Annotated[str | None, Query(max_length=32)] = None,
    ):
        device = config.devices.get(device_id)
        authenticate(authorization, device)
        now = int(clock())
        headers = {"X-InfraBadge-Now": str(now), "Cache-Control": "private, no-cache"}
        fault = fault or device.fault
        if fault:
            if not config.enable_faults or device.node_id is not None:
                raise HTTPException(404, "fault injection disabled")
            if fault == "json":
                return Response("{broken", media_type="application/json", headers=headers)
            if fault == "oversize":
                return Response("x" * 4096, media_type="application/json", headers=headers)
            if fault == "auth":
                raise HTTPException(401, "simulated rejection")
            if fault == "http":
                raise HTTPException(503, "simulated unavailability")
            if fault not in ("expired", "version"):
                raise HTTPException(404, "unknown fault")
        with lock:
            old = cached.get(device_id)
            if device.node_id is not None:
                candidate = nodes[device.node_id].snapshot(
                    device_id, config.collectors[device.node_id], now, old.revision if old else 1
                )
                if old and old.generated_at <= now and candidate.generated_at < old.generated_at:
                    # A late-but-fresh recovery must not go backwards after an
                    # UNKNOWN control response. Expiry still belongs to the sample.
                    candidate = candidate.model_copy(update={"generated_at": old.generated_at})
                # An unchanged stale control representation can also be cached, but
                # a real sample's expiry is never extended by GET or 304.
                unchanged_stale = (
                    old
                    and old.alerts == candidate.alerts
                    and old.status == candidate.status
                    and candidate.alerts[0].detail in ("SIN MUESTRA", "DATOS CADUCADOS")
                    and old.generated_at <= now < old.expires_at
                )
                if unchanged_stale:
                    candidate = old
                elif old and old != candidate:
                    candidate = candidate.model_copy(update={"revision": old.revision + 1})
                old = candidate
                cached[device_id] = old
            elif not old or now >= old.expires_at or old.status != device.scenario:
                old = fixture(
                    device_id,
                    device.scenario,
                    now,
                    old.revision + 1 if old else 1,
                    snapshot_ttl_seconds,
                )
                cached[device_id] = old
            data = old.model_dump()
            if fault == "expired":
                data.update(generated_at=now - 3600, expires_at=now - 1)
            if fault == "version":
                data["schema_version"] = 99
            body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("ascii")
            etag = '"' + hashlib.sha256(body).hexdigest() + '"'
        headers["ETag"] = etag
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type="application/json", headers=headers)

    return app
