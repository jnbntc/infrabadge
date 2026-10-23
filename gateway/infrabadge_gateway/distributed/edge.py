"""TLS-only, fixed-upstream edge. No persisted cache, ingestion or admin path."""

import asyncio
import hashlib
import re
import ssl
import time
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator
from starlette.responses import JSONResponse, Response

from ..app import bounded_json
from ..base import DeviceId, Strict
from ..models import Snapshot
from .limits import Budget
from .presentation import Presentation


class EdgeConfig(Strict):
    presentation_v2: bool = False
    upstream: str
    device_ids: Annotated[list[DeviceId], Field(min_length=1, max_length=16)]
    ca_file: str
    credential_file: str
    public_hostname: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,126}[a-z0-9]$")]
    public_port: Annotated[int, Field(ge=1024, le=65535)] = 8443

    @model_validator(mode="after")
    def verified_origin(self):
        url = urlsplit(self.upstream)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or len(set(self.device_ids)) != len(self.device_ids)
        ):
            raise ValueError("fixed HTTPS origin and finite devices required")
        return self


class Edge:
    def __init__(self, config, client, credential, clock=time.time):
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,96}", credential):
            raise ValueError("private edge credential")
        self.config, self.client, self.credential, self.clock = config, client, credential, clock
        self.global_budget = Budget(120, 20)
        self.device_budgets = {d: Budget(12, 6) for d in config.device_ids}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await self.client.aclose()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return

        async def reject(status):
            await JSONResponse(
                {"detail": "edge unavailable" if status == 503 else "request rejected"},
                status_code=status,
                headers={"Cache-Control": "no-store"},
            )(scope, receive, send)

        if not self.global_budget.take():
            return await reject(429)
        match = re.fullmatch(r"/api/v[12]/devices/([a-z0-9][a-z0-9_-]{0,31})/status", scope["path"])
        is_v2 = scope["path"].startswith("/api/v2/")
        if (
            (is_v2 and not self.config.presentation_v2)
            or scope["method"] != "GET"
            or not match
            or match[1] not in self.device_budgets
            or scope.get("query_string")
            or scope.get("raw_path", scope["path"].encode()) != scope["path"].encode()
        ):
            return await reject(404)
        headers = {}
        if sum(len(k) + len(v) for k, v in scope["headers"]) > 8192:
            return await reject(431)
        for k, v in scope["headers"]:
            headers.setdefault(k.lower(), []).append(v)
        if headers.get(b"host") != [
            (self.config.public_hostname + ":" + str(self.config.public_port)).encode()
        ]:
            return await reject(400)
        authorization = headers.get(b"authorization", [])
        if len(authorization) != 1 or not re.fullmatch(
            rb"Bearer [A-Za-z0-9_-]{32,96}", authorization[0]
        ):
            return await reject(401)
        tags = headers.get(b"if-none-match", [])
        if (
            len(tags) > 1
            or (tags and not re.fullmatch(rb'"[0-9a-f]{64}"', tags[0]))
            or headers.get(b"transfer-encoding")
            or headers.get(b"content-length", [b"0"]) != [b"0"]
            or headers.get(b"content-encoding", [b"identity"]) != [b"identity"]
        ):
            return await reject(400)
        if not self.device_budgets[match[1]].take():
            return await reject(429)
        try:
            async with asyncio.timeout(2):
                message = await receive()
            if message["type"] != "http.request" or message.get("body") or message.get("more_body"):
                return await reject(400)
        except TimeoutError:
            return await reject(408)
        outgoing = {
            "Authorization": authorization[0].decode("ascii"),
            "X-InfraBadge-Edge": "Bearer " + self.credential,
        }
        if is_v2:
            outgoing["Accept-Encoding"] = "identity"
        if tags:
            outgoing["If-None-Match"] = tags[0].decode("ascii")
        try:
            async with asyncio.timeout(6):
                async with self.client.stream(
                    "GET", self.config.upstream.rstrip("/") + scope["path"], headers=outgoing
                ) as remote:
                    body = bytearray()
                    async for part in remote.aiter_raw():
                        if len(body) + len(part) > 4096:
                            raise ValueError("upstream size")
                        body.extend(part)
                    tag = remote.headers.get("etag", "")
                    if remote.headers.get("content-encoding", "identity") != "identity":
                        raise ValueError("encoding")
                    if remote.status_code == 401:
                        return await reject(401)
                    if remote.status_code == 403:
                        return await reject(403)
                    if not re.fullmatch(r'"[0-9a-f]{64}"', tag):
                        raise ValueError("upstream tag")
                    if is_v2:
                        server_now = remote.headers.get("x-infrabadge-now", "")
                        expires = remote.headers.get("x-infrabadge-expires", "")
                        if (
                            not re.fullmatch(r"[0-9]{10}", server_now)
                            or not re.fullmatch(r"[0-9]{10}", expires)
                            or abs(int(server_now) - int(self.clock())) > 60
                            or not int(server_now) < int(expires) <= int(server_now) + 3600
                            or int(expires) <= int(self.clock())
                        ):
                            raise ValueError("upstream lifetime")
                    if remote.status_code == 200:
                        if (
                            is_v2
                            and remote.headers.get("content-type", "").split(";")[0]
                            != "application/json"
                        ):
                            raise ValueError("upstream media type")
                        snapshot = (Presentation if is_v2 else Snapshot).model_validate(
                            bounded_json(body)
                        )
                        if (
                            snapshot.device_id != match[1]
                            or (not is_v2 and snapshot.simulated)
                            or (is_v2 and snapshot.expires_at != int(expires))
                            or not snapshot.generated_at <= int(self.clock()) < snapshot.expires_at
                            or tag != '"' + hashlib.sha256(body).hexdigest() + '"'
                        ):
                            raise ValueError("upstream contract")
                    elif remote.status_code != 304 or body or not tags or tags[0].decode() != tag:
                        raise ValueError("upstream response")
                    reply = Response(
                        bytes(body),
                        status_code=remote.status_code,
                        headers={
                            k: v
                            for k, v in remote.headers.items()
                            if k.lower()
                            in (
                                "etag",
                                "x-infrabadge-now",
                                "x-infrabadge-expires",
                                "cache-control",
                                "content-type",
                            )
                        },
                    )
        except (httpx.HTTPError, TimeoutError, ValueError, UnicodeError, RecursionError):
            return await reject(503)
        await reply(scope, receive, send)


def upstream_client(config):
    context = ssl.create_default_context(cafile=config.ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return httpx.AsyncClient(
        verify=context,
        trust_env=False,
        follow_redirects=False,
        timeout=4,
        limits=httpx.Limits(max_connections=16, max_keepalive_connections=4),
    )
