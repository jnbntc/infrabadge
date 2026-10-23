"""M3-compatible ingress plus scoped inventory and M2-compatible snapshots."""

import asyncio
import hashlib
import time

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse, Response

from ..app import authenticate, bounded_json
from ..metrics import Metrics
from .core import Rejected
from .limits import Budget
from .presentation import Presentation, project
from .store import Unavailable


def identity_for(header, identities):
    matched = None
    for identity in identities.values():
        try:
            authenticate(header, identity)
            matched = identity
        except HTTPException:
            pass
    if matched is None:
        authenticate(header, None)
    return matched


def create_app(core, clock=time.time, budget_clock=time.monotonic):
    app = FastAPI(
        title="InfraBadge distributed core", docs_url=None, redoc_url=None, openapi_url=None
    )
    global_budget = Budget(240, 40, budget_clock)
    budgets = {node: Budget(6, 2, budget_clock) for node in core.config.collectors}
    device_budgets = {device: Budget(12, 6, budget_clock) for device in core.config.devices}
    slots = asyncio.Semaphore(16)

    @app.middleware("http")
    async def bounded(request, call_next):
        headers = request.scope["headers"]
        if sum(len(k) + len(v) for k, v in headers) > 8192:
            return JSONResponse({"detail": "headers rejected"}, 431)
        if any(
            sum(k.lower() == name for k, v in headers) > 1
            for name in (b"authorization", b"x-infrabadge-edge")
        ):
            return JSONResponse({"detail": "authentication rejected"}, 401)
        if any(
            len(v) > 103
            for k, v in headers
            if k.lower() in (b"authorization", b"x-infrabadge-edge")
        ):
            return JSONResponse({"detail": "authentication rejected"}, 401)
        if request.url.query:
            return JSONResponse({"detail": "query rejected"}, 400)
        if not global_budget.take():
            return JSONResponse({"detail": "rate limited"}, 429, headers={"Retry-After": "10"})
        try:
            async with asyncio.timeout(0.1):
                await slots.acquire()
        except TimeoutError:
            return JSONResponse({"detail": "capacity unavailable"}, 503)
        try:
            return await call_next(request)
        finally:
            slots.release()

    @app.exception_handler(Rejected)
    async def rejected(request, error):
        return JSONResponse({"detail": "sample rejected"}, error.status)

    @app.exception_handler(Unavailable)
    async def unavailable(request, error):
        return JSONResponse({"detail": "core unavailable"}, 503, headers={"Retry-After": "10"})

    @app.post("/api/v1/collectors/{node_id}/metrics", status_code=202)
    async def ingest(node_id: str, request: Request):
        authenticate(request.headers.get("authorization"), core.config.collectors.get(node_id))
        if not budgets[node_id].take():
            raise HTTPException(429, "rate limited")
        if (
            request.headers.get("content-type", "").split(";")[0] != "application/json"
            or request.headers.get("content-encoding", "identity") != "identity"
        ):
            raise HTTPException(415, "JSON required")
        body = bytearray()
        try:
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    if len(body) + len(chunk) > 8192:
                        raise HTTPException(413, "payload rejected")
                    body.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "body deadline") from None
        try:
            sample = Metrics.model_validate(bounded_json(body))
        except (ValueError, UnicodeError, RecursionError):
            raise HTTPException(422, "metrics rejected") from None
        # No awaited network I/O occurs within the SQLite transaction.
        try:
            await asyncio.to_thread(core.ingest, node_id, sample, int(clock()))
        except (ValueError, KeyError, TypeError):
            raise Unavailable("stored data rejected") from None
        return {"accepted": True}

    @app.get("/api/v1/devices/{device_id}/status")
    def status(device_id: str, request: Request):
        authenticate(request.headers.get("authorization"), core.config.devices.get(device_id))
        if core.config.require_edge:
            edge = identity_for(request.headers.get("x-infrabadge-edge"), core.config.edges)
            if device_id not in edge.device_ids:
                raise HTTPException(403, "scope rejected")
        if not device_budgets[device_id].take():
            raise HTTPException(429, "rate limited")
        now = int(clock())
        try:
            body = core.snapshot(device_id, now)
        except (ValueError, KeyError, TypeError):
            raise Unavailable("stored data rejected") from None
        tag = '"' + hashlib.sha256(body).hexdigest() + '"'
        headers = {"ETag": tag, "X-InfraBadge-Now": str(now), "Cache-Control": "private, no-cache"}
        if request.headers.get("if-none-match") == tag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type="application/json", headers=headers)

    @app.get("/api/v2/devices/{device_id}/status")
    def presentation(device_id: str, request: Request):
        authenticate(request.headers.get("authorization"), core.config.devices.get(device_id))
        if core.config.require_edge:
            edge = identity_for(request.headers.get("x-infrabadge-edge"), core.config.edges)
            if device_id not in edge.device_ids:
                raise HTTPException(403, "scope rejected")
        if not core.config.devices[device_id].presentation_v2:
            raise HTTPException(404, "presentation not enabled")
        if not device_budgets[device_id].take():
            raise HTTPException(429, "rate limited")
        now = int(clock())
        try:
            body = project(core, device_id, now)
            expires = Presentation.model_validate_json(body).expires_at
        except (ValueError, KeyError, TypeError):
            raise Unavailable("projection unavailable") from None
        tag = '"' + hashlib.sha256(body).hexdigest() + '"'
        metadata = {
            "ETag": tag,
            "X-InfraBadge-Now": str(now),
            "X-InfraBadge-Expires": str(expires),
            "Cache-Control": "private, no-cache",
        }
        if request.headers.get("if-none-match") == tag:
            return Response(status_code=304, headers=metadata)
        return Response(body, media_type="application/json", headers=metadata)

    @app.get("/api/v1/sites/{site_id}/nodes")
    def inventory(site_id: str, request: Request):
        identity = identity_for(request.headers.get("authorization"), core.config.readers)
        if site_id not in identity.site_ids:
            raise HTTPException(403, "scope rejected")
        try:
            return core.inventory(site_id, int(clock()))
        except (ValueError, KeyError, TypeError):
            raise Unavailable("stored data rejected") from None

    return app
