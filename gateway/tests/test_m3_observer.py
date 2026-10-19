"""M3 lab observer: deterministic fixtures, no USB or selected LAN binding."""

import asyncio
import hashlib
import json
import ssl

import httpx
import pytest
from infrabadge_gateway.app import create_app
from infrabadge_gateway.models import Device, GatewayConfig, Snapshot
from lab_support import loopback
from observe_gateway import Evidence, create_observer, serve_bounded

NOW = 1800000000
TOKEN, COLLECTOR = "d" * 40, "c" * 40
PATH = "/api/v1/devices/badge-lab/status"


def identity():
    return Device(node_id="workstation", token_sha256=[hashlib.sha256(TOKEN.encode()).hexdigest()])


def sample(now):
    return dict(
        schema_version=1,
        node_id="workstation",
        collector_version="0.3.0",
        collected_at=now,
        cpu=dict(usage_percent=20.0, logical_cpus=4, load_average=[1.0, 1.0, 1.0]),
        memory=dict(
            total_bytes=10000,
            available_bytes=7000,
            used_bytes=3000,
            used_percent=30.0,
            available_estimated=False,
        ),
        disk=dict(mount_id="HOME", total_bytes=10000, available_bytes=6000, used_percent=40.0),
        temperature=None,
        uptime_seconds=float(now - NOW + 1000),
        errors=["temperature_unavailable"],
    )


def configuration():
    return GatewayConfig.model_validate(
        dict(
            devices={"badge-lab": identity().model_dump()},
            collectors={
                "workstation": dict(
                    display_name="WORKSTATION",
                    token_sha256=[hashlib.sha256(COLLECTOR.encode()).hexdigest()],
                )
            },
        )
    )


def test_gateway_contract_etag_stale_and_recovery_unchanged():
    async def scenario():
        now = [NOW]
        gateway = create_app(configuration(), clock=lambda: now[0])
        evidence = Evidence(clock=lambda: now[0])
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(gateway), base_url="https://localhost"
        ) as backend:
            response = await backend.post(
                "/api/v1/collectors/workstation/metrics",
                json=sample(now[0]),
                headers={"Authorization": "Bearer " + COLLECTOR},
            )
            assert response.status_code == 202
            observer = create_observer("badge-lab", identity(), backend, evidence)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(observer), base_url="https://lab"
            ) as client:
                headers = {"Authorization": "Bearer " + TOKEN}
                first = await client.get(PATH, headers=headers)
                direct = await backend.get(PATH, headers=headers)
                assert first.status_code == 200 and first.content == direct.content
                assert first.headers["etag"] == direct.headers["etag"]
                snapshot = Snapshot.model_validate(first.json())
                assert not snapshot.simulated and snapshot.expires_at == NOW + 180
                now[0] += 60
                conditional = {**headers, "If-None-Match": first.headers["etag"]}
                same = await client.get(PATH, headers=conditional)
                assert same.status_code == 304 and same.content == b""
                assert same.headers["x-infrabadge-now"] == str(now[0])
                now[0] = NOW + 180
                stale = await client.get(PATH, headers=conditional)
                assert stale.status_code == 200
                assert stale.json()["status"] == "UNKNOWN"
                assert evidence.events[-1]["control"] == "stale"
                assert "CPU 20%" not in stale.text
                response = await backend.post(
                    "/api/v1/collectors/workstation/metrics",
                    json=sample(now[0]),
                    headers={"Authorization": "Bearer " + COLLECTOR},
                )
                assert response.status_code == 202
                recovered = await client.get(PATH, headers=headers)
                assert recovered.status_code == 200 and recovered.json()["status"] == "HEALTHY"
                assert recovered.json()["expires_at"] == now[0] + 180
                assert evidence.events[-1]["control"] == "fresh"
        assert [e["http_status"] for e in evidence.events] == [200, 304, 200, 200]
        serialized = json.dumps(list(evidence.events))
        assert TOKEN not in serialized and COLLECTOR not in serialized
        assert "badge-lab" not in serialized and "workstation" not in serialized
        assert "CPU" not in serialized and "etag" not in serialized

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer " + COLLECTOR},
        [("Authorization", "Bearer " + TOKEN), ("Authorization", "Bearer " + TOKEN)],
    ],
)
def test_authentication_rejected_before_any_upstream(headers):
    async def scenario():
        def unexpected(request):
            raise AssertionError("No upstream access for rejected credentials")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(unexpected), base_url="https://localhost"
        ) as backend:
            evidence = Evidence()
            app = create_observer("badge-lab", identity(), backend, evidence)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://lab"
            ) as client:
                reply = await client.get(PATH, headers=headers)
                assert reply.status_code == 401
                assert evidence.events[-1]["outcome"] == "authentication_rejected"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "path,method,extra",
    [
        (PATH + "?fault=auth", "GET", {}),
        (PATH, "GET", {"If-None-Match": "unbounded-invalid-tag"}),
        (PATH, "GET", {"Content-Length": "1"}),
        (PATH, "POST", {}),
        ("/api/v1/collectors/workstation/metrics", "POST", {}),
        ("/api/v1/devices/another/status", "GET", {}),
    ],
)
def test_not_an_open_proxy_and_no_ingress(path, method, extra):
    async def scenario():
        def unexpected(request):
            raise AssertionError("Rejected request forwarded")

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(unexpected), base_url="https://localhost"
        ) as backend:
            app = create_observer("badge-lab", identity(), backend, Evidence())
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://lab"
            ) as client:
                reply = await client.request(
                    method, path, headers={"Authorization": "Bearer " + TOKEN, **extra}
                )
                assert reply.status_code in (400, 404, 405)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kind",
    [
        "json",
        "oversize",
        "redirect",
        "etag",
        "clock",
        "wrong_id",
        "simulated",
        "expired",
        "unsolicited304",
        "wrong304",
    ],
)
def test_invalid_upstream_is_generic_and_not_a_valid_observation(kind):
    async def scenario():
        secret = "PRIVATE-UPSTREAM-RESPONSE"

        def response(request):
            assert "x-private-probe" not in request.headers
            assert request.headers["accept"] == "application/json"
            payload = Snapshot(
                schema_version=1,
                device_id="badge-lab",
                revision=1,
                simulated=False,
                generated_at=NOW,
                expires_at=NOW + 180,
                status="HEALTHY",
                counts=dict(healthy=1, warning=0, critical=0, unknown=0),
                alerts=[],
            ).model_dump()
            if kind == "wrong_id":
                payload["device_id"] = "other"
            if kind == "simulated":
                payload["simulated"] = True
            if kind == "expired":
                payload.update(generated_at=NOW - 200, expires_at=NOW - 1)
            body = json.dumps(payload).encode()
            if kind == "json":
                body = secret.encode()
            if kind == "oversize":
                body = b"x" * 2049
            code = 302 if kind == "redirect" else 304 if kind.endswith("304") else 200
            if code == 304:
                body = b""
            tag = '"' + hashlib.sha256(body).hexdigest() + '"'
            if kind == "etag":
                tag = '"' + "0" * 64 + '"'
            headers = {
                "ETag": tag,
                "X-InfraBadge-Now": str(NOW),
                "Content-Type": "application/json",
                "Location": "https://untrusted.invalid/",
            }
            if kind == "clock":
                headers["X-InfraBadge-Now"] = "invalid"
            return httpx.Response(code, content=body, headers=headers)

        evidence = Evidence(clock=lambda: NOW)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(response),
            base_url="https://localhost",
            follow_redirects=False,
        ) as backend:
            app = create_observer("badge-lab", identity(), backend, evidence)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://lab"
            ) as client:
                headers = {"Authorization": "Bearer " + TOKEN, "X-Private-Probe": secret}
                if kind == "wrong304":
                    headers["If-None-Match"] = '"' + "f" * 64 + '"'
                reply = await client.get(PATH, headers=headers)
                assert reply.status_code == 502
                assert secret not in reply.text and TOKEN not in reply.text
                assert evidence.events[-1]["outcome"] == "upstream_invalid"
                assert secret not in json.dumps(list(evidence.events))

    asyncio.run(scenario())


def test_upstream_timeout_no_exception_or_credentials_echo():
    async def scenario():
        def timeout(request):
            raise httpx.ReadTimeout("PRIVATE TRACE " + TOKEN)

        evidence = Evidence()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(timeout), base_url="https://localhost"
        ) as backend:
            app = create_observer("badge-lab", identity(), backend, evidence)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://lab"
            ) as client:
                reply = await client.get(PATH, headers={"Authorization": "Bearer " + TOKEN})
                assert reply.status_code == 504 and "PRIVATE" not in reply.text
                assert evidence.events[-1]["outcome"] == "upstream_unavailable"

    asyncio.run(scenario())


def test_private_bounded_evidence_and_refuse_existing_or_symlink(tmp_path):
    tmp_path.chmod(0o700)
    out = tmp_path / "events.json"
    evidence = Evidence(out, capacity=2, clock=lambda: NOW)
    for _ in range(5):
        evidence.record("completed", 200, False, "HEALTHY", "fresh")
    rows = json.loads(out.read_text())["events"]
    assert [r["sequence"] for r in rows] == [4, 5]
    assert out.stat().st_mode & 0o077 == 0
    with pytest.raises(ValueError):
        Evidence(out)
    link = tmp_path / "link.json"
    link.symlink_to(out)
    with pytest.raises(ValueError):
        Evidence(link)
    with pytest.raises(ValueError):
        evidence.record("RAW SECRET", 200, False)
    assert len(json.loads(out.read_text())["events"]) == 2


def test_server_lifetime_bounds_shutdown_and_closes_upstream():
    class Server:
        should_exit = False

        async def serve(self):
            while not self.should_exit:
                await asyncio.sleep(0.001)

    class Backend:
        closed = False

        async def aclose(self):
            self.closed = True

    server, backend = Server(), Backend()
    asyncio.run(serve_bounded(server, backend, seconds=0.01))
    assert server.should_exit and backend.closed


@pytest.mark.parametrize("kind", ["valid", "expired", "wronghost"])
def test_actual_upstream_tls_ca_hostname_dates(tmp_path, kind):
    with loopback(tmp_path, clock=lambda: NOW, certificate_kind=kind) as (config, _token, device):

        async def scenario():
            context = ssl.create_default_context(cafile=config["ca_file"])
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            async with httpx.AsyncClient(
                base_url=config["gateway_url"], verify=context, trust_env=False, timeout=3
            ) as backend:
                expected = Device(
                    node_id="workstation",
                    token_sha256=[hashlib.sha256(device.encode()).hexdigest()],
                )
                evidence = Evidence()
                app = create_observer("badge-lab", expected, backend, evidence)
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app), base_url="https://lab"
                ) as client:
                    reply = await client.get(PATH, headers={"Authorization": "Bearer " + device})
                    assert reply.status_code == (200 if kind == "valid" else 504)
                    assert evidence.events[-1]["outcome"] == (
                        "completed" if kind == "valid" else "upstream_unavailable"
                    )
                    if kind == "valid":
                        assert reply.json()["alerts"][0]["detail"] == "SIN MUESTRA"

        asyncio.run(scenario())


def test_server_failure_still_closes_upstream():
    class Server:
        should_exit = False

        async def serve(self):
            raise OSError("fixture listen failure")

    class Backend:
        closed = False

        async def aclose(self):
            self.closed = True

    backend = Backend()
    with pytest.raises(OSError):
        asyncio.run(serve_bounded(Server(), backend, seconds=0.01))
    assert backend.closed


def test_unknown_ca_check_cannot_pass_on_connection_refused():
    from check_observer import certificate_rejection

    cause = ssl.SSLCertVerificationError("fixture")
    outer = httpx.ConnectError("fixture")
    outer.__cause__ = cause
    assert certificate_rejection(outer)
    assert not certificate_rejection(httpx.ConnectError("connection refused"))


@pytest.mark.parametrize(
    "address", ["0.0.0.0", "127.0.0.1", "169.254.1.1", "239.0.0.1", "::", "8.8.8.8"]
)
def test_listener_rejects_wildcards_and_unselected_address_classes(address):
    from observe_gateway import selected_address

    with pytest.raises(ValueError):
        selected_address(address)


def test_total_deadline_not_only_transport_timeout(monkeypatch):
    original = asyncio.timeout
    monkeypatch.setattr("observe_gateway.asyncio.timeout", lambda seconds: original(0.01))

    async def scenario():
        async def slow(request):
            await asyncio.sleep(0.2)
            return httpx.Response(200, json={"private": "not exposed"})

        evidence = Evidence()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(slow), base_url="https://localhost"
        ) as backend:
            app = create_observer("badge-lab", identity(), backend, evidence)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://lab"
            ) as client:
                reply = await client.get(PATH, headers={"Authorization": "Bearer " + TOKEN})
                assert reply.status_code == 504 and "private" not in reply.text
                assert evidence.events[-1]["outcome"] == "upstream_unavailable"

    asyncio.run(scenario())
