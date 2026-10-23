"""M3.5 software integration: scoped Core -> Edge -> actual C -> framebuffer."""

import asyncio
import hashlib
import json
import os
import ssl
import subprocess
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.edge import Edge, EdgeConfig, upstream_client
from infrabadge_gateway.distributed.presentation import Presentation, project
from infrabadge_gateway.distributed.store import Store
from infrabadge_gateway.lab import certificates
from m32_fixtures import NOW, TOKENS, headers, sample
from wire_fixtures import body, config

ROOT = Path(__file__).resolve().parents[2]
PATH = "/api/v2/devices/display-a/status"


class Parts(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body

    async def __aiter__(self):
        yield self.body


def edge_config(**changes):
    return EdgeConfig(
        upstream="https://central.test:9443",
        device_ids=["display-a"],
        ca_file="/private/ca.pem",
        credential_file="/private/edge.token",
        public_hostname="edge.test",
        presentation_v2=True,
        **changes,
    )


@pytest.fixture
def parts(tmp_path):
    tmp_path.chmod(0o700)
    store = Store(tmp_path / "core.db")
    core = Core(config(), store)
    for n in ("a", "b", "c"):
        core.ingest(n, sample(node=n), NOW)
    now = [NOW]
    with TestClient(create_app(core, clock=lambda: now[0])) as api:
        yield core, api, now
    store.close()


def through_edge(api, now):
    def remote(request):
        r = api.get(request.url.path, headers=dict(request.headers))
        return httpx.Response(r.status_code, headers=r.headers, stream=Parts(r.content))

    return Edge(
        edge_config(),
        httpx.AsyncClient(transport=httpx.MockTransport(remote)),
        TOKENS["e-edge"],
        clock=lambda: now[0],
    )


def test_scoped_projection_roundtrip_and_v1_compatibility(parts):
    core, api, now = parts
    original = core.snapshot("display-a", NOW)
    with TestClient(through_edge(api, now), base_url="https://edge.test:8443") as client:
        r = client.get(PATH, headers=headers("d-device"))
        assert r.status_code == 200
        model = Presentation.model_validate_json(r.content)
        assert len(r.content) <= 4096 and len(model.nodes) == 3 and model.sites[2].name == "TRABAJO"
        assert model.sites[2].status == "UNKNOWN" and not [
            n for n in model.nodes if n.site == "work"
        ]
        assert r.content == project(core, "display-a", NOW)
        assert (
            client.get(
                PATH, headers=headers("d-device", **{"If-None-Match": r.headers["etag"]})
            ).status_code
            == 304
        )
        assert (
            client.get("/api/v1/devices/display-a/status", headers=headers("d-device")).content
            == original
        )
    assert core.store.db.execute("PRAGMA user_version").fetchone() == (2,)


@pytest.mark.parametrize("role", ["collector-a", "r-reader", "f-device", "g-edge"])
def test_auth_roles_cannot_read_another_device(parts, role):
    _, api, now = parts
    with TestClient(through_edge(api, now), base_url="https://edge.test:8443") as client:
        assert client.get(PATH, headers=headers(role)).status_code == 401
    assert api.get(PATH, headers=headers("d-device", "g-edge")).status_code == 403


def test_opt_in_and_finite_edge_paths(parts):
    core, api, now = parts
    assert (
        api.get(
            "/api/v2/devices/display-b/status", headers=headers("f-device", "g-edge")
        ).status_code
        == 404
    )
    with TestClient(through_edge(api, now), base_url="https://edge.test:8443") as client:
        for path in (
            "/api/v1/sites/alpha/nodes",
            PATH + "?x=1",
            PATH.replace("display-a", "display-b"),
            "/api/v2/collectors/a/metrics",
        ):
            assert client.get(path, headers=headers("d-device")).status_code == 404
    edge = through_edge(api, now)
    edge.config = edge.config.model_copy(update={"presentation_v2": False})
    with TestClient(edge, base_url="https://edge.test:8443") as client:
        assert client.get(PATH, headers=headers("d-device")).status_code == 404


def test_ttl_304_stale_offline_and_real_recovery(parts):
    core, api, now = parts
    with TestClient(through_edge(api, now), base_url="https://edge.test:8443") as client:
        r = client.get(PATH, headers=headers("d-device"))
        tag = r.headers["etag"]
        expires = r.json()["expires_at"]
        now[0] += 60
        unchanged = client.get(PATH, headers=headers("d-device", **{"If-None-Match": tag}))
        assert (
            unchanged.status_code == 304
            and int(unchanged.headers["x-infrabadge-expires"]) == expires
        )
        now[0] = expires
        stale = client.get(PATH, headers=headers("d-device", **{"If-None-Match": tag}))
        assert stale.status_code == 200
        assert stale.json()["status"] == "UNKNOWN"
        assert all(
            n["cpu"] is None and n["ram"] is None and n["disk"] is None
            for n in stale.json()["nodes"]
        )
        now[0] = NOW + 601
        offline = client.get(PATH, headers=headers("d-device"))
        assert offline.json()["status"] == "OFFLINE"
        for n in ("a", "b", "c"):
            core.ingest(n, sample(node=n, at=now[0]), now[0])
        assert client.get(PATH, headers=headers("d-device")).json()["status"] == "HEALTHY"


def test_missing_metrics_and_cpu_latches(parts):
    core, _, _ = parts
    core.ingest("a", sample(at=NOW + 30, cpu=99.0), NOW + 30)
    assert not project(core, "display-a", NOW + 30) == b""
    first = json.loads(project(core, "display-a", NOW + 30))
    assert first["status"] == "HEALTHY" and not first["alerts"]
    core.ingest("a", sample(at=NOW + 60, cpu=99.0), NOW + 60)
    core.ingest("a", sample(at=NOW + 90, cpu=99.0), NOW + 90)
    critical = json.loads(project(core, "display-a", NOW + 90))
    assert critical["status"] == "CRITICAL" and critical["alerts"][0]["metric"] == "CPU"
    assert critical["alerts"][0]["value"] == 990


@pytest.mark.parametrize(
    "failure",
    [
        "timeout",
        "oversize",
        "malformed",
        "wrong_device",
        "expired",
        "bad_etag",
        "bad304",
        "missing_lifetime",
    ],
)
def test_upstream_errors_fail_closed_then_recover(parts, failure):
    core, _, now = parts
    healthy = project(core, "display-a", NOW)
    failed = [True]

    def remote(request):
        raw = json.loads(healthy)
        content = healthy
        if failed[0]:
            if failure == "timeout":
                raise httpx.ConnectTimeout("private")
            if failure == "oversize":
                content = b"x" * 4097
            elif failure == "malformed":
                content = b"{}"
            elif failure == "wrong_device":
                raw["device_id"] = "other"
                content = json.dumps(raw).encode()
            elif failure == "expired":
                raw["expires_at"] = NOW - 1
                content = json.dumps(raw).encode()
        tag = '"' + hashlib.sha256(content).hexdigest() + '"'
        metadata = {
            "etag": tag,
            "x-infrabadge-now": str(NOW),
            "x-infrabadge-expires": str(NOW + 180),
            "content-type": "application/json",
        }
        if failed[0] and failure == "bad_etag":
            metadata["etag"] = '"' + "0" * 64 + '"'
        if failed[0] and failure == "missing_lifetime":
            del metadata["x-infrabadge-expires"]
        return httpx.Response(
            304 if failed[0] and failure == "bad304" else 200,
            headers=metadata,
            stream=Parts(content),
        )

    edge = Edge(
        edge_config(),
        httpx.AsyncClient(transport=httpx.MockTransport(remote)),
        TOKENS["e-edge"],
        clock=lambda: now[0],
    )
    with TestClient(edge, base_url="https://edge.test:8443") as client:
        assert client.get(PATH, headers=headers("d-device")).status_code == 503
        failed[0] = False
        assert client.get(PATH, headers=headers("d-device")).status_code == 200


def test_request_rate_limit(parts):
    _, api, now = parts
    with TestClient(through_edge(api, now), base_url="https://edge.test:8443") as client:
        codes = [client.get(PATH, headers=headers("d-device")).status_code for _ in range(9)]
        assert codes[:6] == [200] * 6 and codes[-1] == 429


def test_projection_over_capacity_fails_without_partial_inventory(parts):
    core, api, _ = parts
    for i in range(4):
        core.config.nodes[f"extra{i}"] = core.config.nodes["a"]
    assert api.get(PATH, headers=headers("d-device", "e-edge")).status_code == 503


@pytest.fixture
def native():
    path = Path(os.environ.get("IB_M35_NATIVE", ROOT / "results/m35-native/render"))
    if not path.is_file():
        pytest.skip("Native C executable supplied by SDK regression job")
    return path


def test_edge_to_actual_firmware_parser_and_framebuffer(parts, tmp_path, native):
    _, api, now = parts
    with TestClient(through_edge(api, now), base_url="https://edge.test:8443") as client:
        r = client.get(PATH, headers=headers("d-device"))
        assert r.status_code == 200
    source = tmp_path / "wire.json"
    source.write_bytes(r.content)
    for view in range(5):
        result = subprocess.run(
            [str(native), str(source), str(view), str(NOW)], capture_output=True, check=True
        )
        assert result.stdout.startswith(b"P4\n200 200\n") and len(result.stdout) == 5011


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "wrong_identity",
        "unknown_field",
        "future_sample",
        "stale_metric",
        "negative",
        "overflow",
        "sites",
        "nodes",
        "alerts",
        "aggregate",
        "schema",
        "unicode",
        "nul",
        "oversize",
    ],
)
def test_c_parser_rejects_invalid_transactionally(tmp_path, native, case):
    raw = json.loads((ROOT / "tests/fixtures/m35-wire/healthy.json").read_bytes())
    if case == "wrong_identity":
        raw["device_id"] = "other"
    elif case == "unknown_field":
        raw["admin"] = True
    elif case == "future_sample":
        raw["nodes"][0]["sampled_at"] = NOW + 1
    elif case == "stale_metric":
        raw["nodes"][0]["valid_until"] = None
    elif case == "negative":
        raw["nodes"][0]["cpu"] = -1
    elif case == "overflow":
        raw["nodes"][0]["temperature"] = 15001
    elif case == "sites":
        raw["sites"] *= 2
    elif case == "nodes":
        raw["nodes"] *= 3
    elif case == "alerts":
        raw["alerts"] = [{}] * 5
    elif case == "aggregate":
        raw["status"] = "CRITICAL"
    elif case == "schema":
        raw["schema_version"] = 1
    elif case == "unicode":
        raw["nodes"][0]["name"] = "NÓDO"
    content = json.dumps(raw, separators=(",", ":")).encode()
    if case == "duplicate":
        content = content.replace(b'"schema_version":2', b'"schema_version":2,"schema_version":2')
    if case == "nul":
        content += b"\x00"
    if case == "oversize":
        content += b" " * 4096
    source = tmp_path / "bad.json"
    source.write_bytes(content)
    result = subprocess.run([str(native), str(source), "0", str(NOW)], capture_output=True)
    assert result.returncode == 4, (case, result.stderr)


def test_fixtures_reproduce_core(tmp_path):
    for scenario in ("healthy", "warning", "critical", "missing", "stale", "offline"):
        folder = tmp_path / scenario
        folder.mkdir(mode=0o700)
        assert json.loads(body(folder, scenario)) == json.loads(
            (ROOT / "tests/fixtures/m35-wire" / (scenario + ".json")).read_bytes()
        )


@pytest.mark.parametrize("kind", ["valid", "wronghost", "expired", "foreignca"])
def test_v2_real_two_hop_tls(parts, tmp_path, kind):
    # Ephemeral loopback test listeners only; no host/LAN deployment or board.
    from gateway.tests.test_m32_edge import tls_server

    core, _, now = parts
    folder = tmp_path / "tls"
    folder.mkdir()
    ca, cert, key = certificates(folder, kind=kind if kind in ("wronghost", "expired") else "valid")
    context = ssl.create_default_context(cafile=str(ca))
    if kind == "foreignca":
        context = ssl.create_default_context()
    with tls_server(create_app(core, clock=lambda: now[0]), cert, key) as origin:
        upstream = httpx.AsyncClient(verify=context, trust_env=False, timeout=2)
        cfg = edge_config().model_copy(update={"upstream": origin})
        edge = Edge(cfg, upstream, TOKENS["e-edge"], clock=lambda: now[0])
        if kind == "valid":
            with tls_server(edge, cert, key) as address:
                with httpx.Client(verify=context, trust_env=False, timeout=2) as client:
                    r = client.get(
                        address + PATH, headers=headers("d-device", **{"Host": "edge.test:8443"})
                    )
                    assert r.status_code == 200 and len(r.json()["nodes"]) == 3
                    executable = Path(
                        os.environ.get("IB_M35_NATIVE", ROOT / "results/m35-native/render")
                    )
                    if executable.is_file():
                        wire = tmp_path / "two-hop.json"
                        wire.write_bytes(r.content)
                        result = subprocess.run(
                            [str(executable), str(wire), "0", str(NOW)],
                            capture_output=True,
                            check=True,
                        )
                        assert len(result.stdout) == 5011 and result.stdout.startswith(
                            b"P4\n200 200\n"
                        )
        else:
            with TestClient(edge, base_url="https://edge.test:8443") as client:
                assert client.get(PATH, headers=headers("d-device")).status_code == 503
        asyncio.run(upstream.aclose())


def test_client_config_always_verifies(tmp_path):
    ca, _, _ = certificates(tmp_path)
    cfg = edge_config().model_copy(update={"ca_file": str(ca)})
    client = upstream_client(cfg)
    assert client.trust_env is False and client.follow_redirects is False
    asyncio.run(client.aclose())


def test_device_scope_does_not_leak_other_site(parts):
    core, api, _ = parts
    core.config.devices["display-b"].presentation_v2 = True
    r = api.get("/api/v2/devices/display-b/status", headers=headers("f-device", "g-edge"))
    assert r.status_code == 200
    assert [n["id"] for n in r.json()["nodes"]] == ["b"]
    assert [s["id"] for s in r.json()["sites"]] == ["beta"]
    assert api.get(PATH, headers=headers("f-device", "g-edge")).status_code == 401


def test_expired_304_from_upstream_is_not_forwarded(parts):
    _, _, now = parts

    def remote(request):
        return httpx.Response(
            304,
            headers={
                "etag": '"' + "a" * 64 + '"',
                "x-infrabadge-now": str(NOW),
                "x-infrabadge-expires": str(NOW),
            },
            stream=Parts(b""),
        )

    edge = Edge(
        edge_config(),
        httpx.AsyncClient(transport=httpx.MockTransport(remote)),
        TOKENS["e-edge"],
        clock=lambda: now[0],
    )
    with TestClient(edge, base_url="https://edge.test:8443") as client:
        assert (
            client.get(
                PATH, headers=headers("d-device", **{"If-None-Match": '"' + "a" * 64 + '"'})
            ).status_code
            == 503
        )


def test_inert_edge_template_validates_without_private_files():
    cfg = EdgeConfig.model_validate_json((ROOT / "deploy/m35/edge.example.json").read_bytes())
    assert cfg.presentation_v2 and cfg.public_port == 8443


def test_maximum_wire_cardinality_and_extreme_metrics(tmp_path, native):
    raw = json.loads((ROOT / "tests/fixtures/m35-wire/healthy.json").read_bytes())
    template = raw["nodes"][0]
    raw["nodes"] = []
    for i in range(6):
        n = template.copy()
        n.update(
            id=("n" * 31) + str(i),
            name="ABCDEFGHIJKL",
            cpu=1000,
            ram=1000,
            disk=1000,
            temperature=-4000,
            status="CRITICAL",
        )
        raw["nodes"].append(n)
    raw["status"] = "CRITICAL"
    raw["sites"][0]["status"] = "CRITICAL"
    raw["sites"][1]["status"] = "UNKNOWN"
    raw["alerts"] = [
        dict(node=("n" * 31) + str(i), severity="CRITICAL", metric="RAM", value=1000, at=NOW)
        for i in range(4)
    ]
    raw["more_alerts"] = 2
    content = json.dumps(raw, separators=(",", ":")).encode()
    assert len(content) <= 4096
    source = tmp_path / "maximum.json"
    source.write_bytes(content)
    Presentation.model_validate(raw)
    for view in range(5):
        assert (
            subprocess.run(
                [str(native), str(source), str(view), str(NOW)], capture_output=True
            ).returncode
            == 0
        )


def test_native_memory_bounds(native):
    result = json.loads(subprocess.check_output([str(native), "--sizes"]))
    assert result["retained_bytes"] <= 7680
    assert result["snapshot_bytes"] <= 1600
    assert result["max_json_bytes"] == 4096 and result["framebuffer_bytes"] == 5000
