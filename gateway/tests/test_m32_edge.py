"""Synthetic edge and two-hop verified TLS. No LAN, Tailscale or board."""

import asyncio
import contextlib
import hashlib
import json
import socket
import ssl
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.edge import Edge, EdgeConfig
from infrabadge_gateway.distributed.store import Store
from infrabadge_gateway.lab import certificates
from m32_fixtures import NOW, TOKENS, configuration, headers, sample


def edge_config():
    return EdgeConfig(
        upstream="https://central.test:9443",
        device_ids=["display-a"],
        ca_file="/private/ca.pem",
        credential_file="/private/edge.token",
        public_hostname="edge.test",
    )


class Parts(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        yield self.body


@pytest.fixture
def core(tmp_path):
    tmp_path.chmod(0o700)
    store = Store(tmp_path / "core.db")
    core = Core(configuration(), store)
    core.ingest("a", sample(), NOW)
    try:
        yield core
    finally:
        store.close()


def response(core, status=200, body=None, tag=None):
    if body is None:
        body = core.snapshot("display-a", NOW)
    tag = tag or '"' + hashlib.sha256(body).hexdigest() + '"'
    return httpx.Response(
        status, headers={"etag": tag, "content-type": "application/json"}, stream=Parts(body)
    )


def test_edge_forwards_exact_contract_and_etag_with_two_identities(core):
    observed = []

    def remote(request):
        observed.append(request)
        assert request.url.host == "central.test"
        assert request.headers["authorization"] == "Bearer " + TOKENS["d-device"]
        assert request.headers["x-infrabadge-edge"] == "Bearer " + TOKENS["e-edge"]
        if request.headers.get("if-none-match"):
            return response(core, 304, b"", request.headers["if-none-match"])
        return response(core)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(remote))
    edge = Edge(edge_config(), upstream, TOKENS["e-edge"], clock=lambda: NOW)
    with TestClient(edge, base_url="https://edge.test:8443") as client:
        first = client.get("/api/v1/devices/display-a/status", headers=headers("d-device"))
        assert first.status_code == 200 and first.content == core.snapshot("display-a", NOW)
        cached = client.get(
            "/api/v1/devices/display-a/status",
            headers=headers("d-device", **{"If-None-Match": first.headers["etag"]}),
        )
        assert cached.status_code == 304 and cached.content == b""
        assert (
            client.post("/api/v1/collectors/a/metrics", headers=headers("d-device")).status_code
            == 404
        )
        assert (
            client.get("/api/v1/sites/alpha/nodes", headers=headers("d-device")).status_code == 404
        )
    asyncio.run(upstream.aclose())
    assert len(observed) == 2


@pytest.mark.parametrize(
    "failure",
    [
        "disconnect",
        "timeout",
        "redirect",
        "wrong_device",
        "oversize",
        "expired",
        "wrong_etag",
        "unauthorized",
        "forbidden",
        "bad304",
    ],
)
def test_edge_upstream_failures_never_relabel_cached_data_as_current(core, failure):
    def remote(request):
        if failure == "disconnect":
            raise httpx.ConnectError("PRIVATE NETWORK")
        if failure == "timeout":
            raise httpx.ReadTimeout("PRIVATE NETWORK")
        if failure == "redirect":
            return httpx.Response(
                302, headers={"location": "https://forbidden.invalid"}, stream=Parts(b"")
            )
        if failure == "oversize":
            return response(core, body=b"x" * 4097)
        if failure == "expired":
            raw = json.loads(core.snapshot("display-a", NOW))
            raw["generated_at"] = NOW - 60
            raw["expires_at"] = NOW - 1
            return response(core, body=json.dumps(raw).encode())
        if failure == "wrong_device":
            raw = json.loads(core.snapshot("display-a", NOW))
            raw["device_id"] = "other"
            return response(core, body=json.dumps(raw).encode())
        if failure == "wrong_etag":
            return response(core, tag='"' + "0" * 64 + '"')
        if failure in ("unauthorized", "forbidden"):
            return httpx.Response(
                401 if failure == "unauthorized" else 403, stream=Parts(b"PRIVATE DATA")
            )
        return response(core, 304, b"", '"' + "0" * 64 + '"')

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(remote))
    with TestClient(
        Edge(edge_config(), upstream, TOKENS["e-edge"], clock=lambda: NOW),
        base_url="https://edge.test:8443",
    ) as client:
        r = client.get("/api/v1/devices/display-a/status", headers=headers("d-device"))
        assert r.status_code == ({"unauthorized": 401, "forbidden": 403}.get(failure, 503))
        assert "PRIVATE" not in r.text and "NODE_A" not in r.text
    asyncio.run(upstream.aclose())


@pytest.mark.parametrize(
    "path,extra,status",
    [
        ("/api/v1/devices/other/status", {}, 404),
        ("/api/v1/devices/%64isplay-a/status", {}, 404),
        ("/api/v1/devices/display-a/status?x=1", {}, 404),
        ("/api/v1/devices/display-a/status", {"Host": "foreign.test:8443"}, 400),
        ("/api/v1/devices/display-a/status", {"Authorization": "Bearer short"}, 401),
        ("/api/v1/devices/display-a/status", {"If-None-Match": "unbounded"}, 400),
        ("/api/v1/devices/display-a/status", {"Content-Length": "1"}, 400),
    ],
)
def test_edge_rejects_before_any_forward(core, path, extra, status):
    def forbidden(request):
        raise AssertionError("Should not forward")

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(forbidden))
    with TestClient(
        Edge(edge_config(), upstream, TOKENS["e-edge"]), base_url="https://edge.test:8443"
    ) as client:
        assert client.get(path, headers=headers("d-device", **extra)).status_code == status
    asyncio.run(upstream.aclose())


@contextlib.contextmanager
def tls_server(app, cert, key):
    channel = socket.socket()
    channel.bind(("127.0.0.1", 0))
    channel.listen(16)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
            access_log=False,
            log_level="critical",
            lifespan="on",
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [channel]}, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            if not thread.is_alive():
                raise AssertionError("TLS fixture stopped")
            time.sleep(0.01)
        assert server.started
        yield "https://localhost:" + str(channel.getsockname()[1])
    finally:
        server.should_exit = True
        thread.join(5)
        channel.close()
        assert not thread.is_alive()


def test_actual_two_hop_tls_uses_explicit_ca_and_never_forwards_collector(core, tmp_path):
    ca, cert, key = certificates(tmp_path)
    context = ssl.create_default_context(cafile=str(ca))
    with tls_server(create_app(core, clock=lambda: NOW), cert, key) as origin:
        upstream = httpx.AsyncClient(verify=context, trust_env=False, timeout=3)
        cfg = edge_config().model_copy(update={"upstream": origin})
        edge = Edge(cfg, upstream, TOKENS["e-edge"], clock=lambda: NOW)
        with tls_server(edge, cert, key) as local:
            with httpx.Client(verify=context, trust_env=False, timeout=3) as client:
                h = headers("d-device", **{"Host": "edge.test:8443"})
                result = client.get(local + "/api/v1/devices/display-a/status", headers=h)
                assert result.status_code == 200 and result.json()["simulated"] is False
                assert (
                    client.get(
                        local + "/api/v1/devices/display-a/status",
                        headers=h | {"If-None-Match": result.headers["etag"]},
                    ).status_code
                    == 304
                )
                assert (
                    client.post(local + "/api/v1/collectors/a/metrics", headers=h).status_code
                    == 404
                )
            with httpx.Client(trust_env=False, timeout=3) as foreign:
                with pytest.raises(httpx.ConnectError) as error:
                    foreign.get(local + "/api/v1/devices/display-a/status", headers=h)
                # Verify this was certificate rejection rather than refused TCP.
                pending = [error.value]
                found = False
                while pending:
                    item = pending.pop()
                    found |= isinstance(item, ssl.SSLCertVerificationError)
                    pending.extend(
                        v
                        for v in (item.__cause__, item.__context__)
                        if v is not None and v is not item
                    )
                assert found
        asyncio.run(upstream.aclose())


@pytest.mark.parametrize(
    "url",
    [
        "http://central.test",
        "https://token@central.test",
        "https://central.test/x",
        "https://central.test?x=y",
    ],
)
def test_edge_origin_cannot_be_client_controlled(url):
    with pytest.raises(ValueError):
        edge_config().model_copy(update={"upstream": url}).__class__.model_validate(
            edge_config().model_dump() | {"upstream": url}
        )


@pytest.mark.parametrize("kind", ["expired", "wronghost"])
def test_upstream_certificate_failure_returns_unavailable_without_http(core, tmp_path, kind):
    folder = tmp_path / "upstream"
    folder.mkdir()
    ca, cert, key = certificates(folder, kind=kind)
    context = ssl.create_default_context(cafile=str(ca))
    with tls_server(create_app(core, clock=lambda: NOW), cert, key) as origin:
        upstream = httpx.AsyncClient(verify=context, trust_env=False, timeout=2)
        cfg = edge_config().model_copy(update={"upstream": origin})
        with TestClient(
            Edge(cfg, upstream, TOKENS["e-edge"], clock=lambda: NOW),
            base_url="https://edge.test:8443",
        ) as client:
            assert (
                client.get(
                    "/api/v1/devices/display-a/status", headers=headers("d-device")
                ).status_code
                == 503
            )
    assert core.store.db.execute("SELECT count(*) FROM snapshots").fetchone() == (0,)


def test_tailnet_unreachable_then_recovers_without_reusing_cached_snapshot(core):
    online = [False]

    def remote(request):
        if not online[0]:
            raise httpx.ConnectError("private network unavailable")
        return response(core)

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(remote))
    with TestClient(
        Edge(edge_config(), upstream, TOKENS["e-edge"], clock=lambda: NOW),
        base_url="https://edge.test:8443",
    ) as client:
        assert (
            client.get("/api/v1/devices/display-a/status", headers=headers("d-device")).status_code
            == 503
        )
        online[0] = True
        assert (
            client.get("/api/v1/devices/display-a/status", headers=headers("d-device")).status_code
            == 200
        )
