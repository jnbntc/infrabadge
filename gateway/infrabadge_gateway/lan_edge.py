"""Device-only ASGI entrance over the SAME M3 application and memory store."""

import asyncio
import re
import time

from fastapi import HTTPException
from starlette.responses import JSONResponse

from .app import authenticate


class Bucket:
    def __init__(self, per_minute, burst, clock=time.monotonic):
        self.rate, self.capacity, self.clock = per_minute / 60, burst, clock
        self.tokens = float(burst)
        self.last = clock()

    def take(self):
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + max(0, now - self.last) * self.rate)
        self.last = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


class LanEntrance:
    def __init__(self, app, config, policy, authorized, telemetry, clock=time.monotonic):
        if any(
            name not in config.devices or config.devices[name].node_id is None
            for name in policy.devices
        ):
            raise ValueError("lan_requires_configured_real_devices")
        self.app, self.config, self.policy = app, config, policy
        self.authorized, self.telemetry = authorized, telemetry
        self.global_limit = Bucket(policy.edge_per_minute, policy.edge_burst, clock)
        self.limits = {
            name: Bucket(policy.device_per_minute, policy.device_burst, clock)
            for name in policy.devices
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        async def reject(code, event, message="request rejected"):
            self.telemetry.emit(event)
            headers = {"Retry-After": "10"} if code in (429, 503) else None
            if code == 401:
                headers = {"WWW-Authenticate": "Bearer"}
            await JSONResponse({"detail": message}, status_code=code, headers=headers)(
                scope, receive, send
            )

        if not self.authorized():
            return await reject(503, "network_unavailable", "LAN unavailable")
        if not self.global_limit.take():
            return await reject(429, "rate_limited")
        match = re.fullmatch(r"/api/v1/devices/([a-z0-9][a-z0-9_-]{0,31})/status", scope["path"])
        if (
            scope["method"] != "GET"
            or not match
            or match[1] not in self.limits
            or scope.get("query_string")
            or scope.get("raw_path", scope["path"].encode()) != scope["path"].encode()
        ):
            return await reject(404, "edge_rejected")
        if sum(len(key) + len(value) for key, value in scope["headers"]) > 8192:
            return await reject(431, "edge_rejected")
        headers = {}
        for key, value in scope["headers"]:
            headers.setdefault(key.lower(), []).append(value)
        host = headers.get(b"host", [])
        if len(host) != 1 or host[0].lower() != (self.policy.hostname + ":8443").encode():
            return await reject(400, "edge_rejected")
        credentials = headers.get(b"authorization", [])
        if len(credentials) != 1 or len(credentials[0]) > 103:
            return await reject(401, "auth_rejected")
        try:
            authenticate(credentials[0].decode("ascii"), self.config.devices[match[1]])
        except (HTTPException, UnicodeError):
            return await reject(401, "auth_rejected")
        tags = headers.get(b"if-none-match", [])
        if (
            len(tags) > 1
            or (tags and not re.fullmatch(rb'"[0-9a-f]{64}"', tags[0]))
            or headers.get(b"transfer-encoding")
            or headers.get(b"content-length", [b"0"]) not in ([b"0"],)
            or headers.get(b"content-encoding", [b"identity"]) != [b"identity"]
        ):
            return await reject(400, "edge_rejected")
        if not self.limits[match[1]].take():
            return await reject(429, "rate_limited")
        try:
            async with asyncio.timeout(2):
                message = await receive()
            if message["type"] != "http.request" or message.get("body") or message.get("more_body"):
                return await reject(400, "edge_rejected")
        except TimeoutError:
            return await reject(408, "edge_rejected")

        async def empty_receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        blocked = False
        self.telemetry.emit("device_query")

        async def gated_send(message):
            nonlocal blocked
            if message["type"] == "http.response.start" and not self.authorized():
                blocked = True
                await reject(503, "network_unavailable", "LAN unavailable")
            elif not blocked:
                if message["type"] == "http.response.start" and message["status"] in (200, 304):
                    self.telemetry.emit("response_delivered")
                await send(message)

        # No new serializer, forwarding client, redirect or second metric store.
        await self.app(scope, empty_receive, gated_send)
