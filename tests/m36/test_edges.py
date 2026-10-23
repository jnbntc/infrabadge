"""Two independent ephemeral TLS edges, real Core, synthetic samples only."""

import asyncio
import hashlib
import ssl

import httpx
import pytest
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.edge import Edge, EdgeConfig
from infrabadge_gateway.distributed.store import Store
from infrabadge_gateway.lab import certificates
from m32_fixtures import NOW, TOKENS, sample
from wire_fixtures import config

from gateway.tests.test_m32_edge import tls_server

PATH = "/api/v2/devices/display-a/status"
HOME = "home-edge-synthetic-" * 3
WORK = "work-edge-synthetic-" * 3


def edge_config(upstream):
    return EdgeConfig(
        upstream=upstream,
        device_ids=["display-a"],
        ca_file="/not-used-by-injected-client",
        credential_file="/not-used-by-injected-client",
        public_hostname="localhost",
        presentation_v2=True,
    )


@pytest.mark.parametrize("kind", ["valid", "wronghost", "foreignca", "expired"])
def test_two_edges_independent_identity_and_verified_tls(tmp_path, kind):
    tmp_path.chmod(0o700)
    store = Store(tmp_path / "core.db")
    cfg = config()
    raw = cfg.model_dump()
    raw["edges"].update(
        {
            name: {
                "token_sha256": [hashlib.sha256(token.encode()).hexdigest()],
                "device_ids": ["display-a"],
            }
            for name, token in (("home-edge", HOME), ("work-edge", WORK))
        }
    )
    core = Core(type(cfg).model_validate(raw), store)
    for node in ("a", "b", "c"):
        core.ingest(node, sample(node=node), NOW)
    clock = [NOW]
    tls = tmp_path / "tls"
    tls.mkdir()
    ca, cert, key = certificates(tls)
    verified = ssl.create_default_context(cafile=str(ca))
    try:
        with tls_server(
            create_app(core, clock=lambda: clock[0], budget_clock=lambda: clock[0]), cert, key
        ) as origin:
            upstream_home = httpx.AsyncClient(verify=verified, trust_env=False, timeout=2)
            upstream_work = httpx.AsyncClient(verify=verified, trust_env=False, timeout=2)
            home = Edge(edge_config(origin), upstream_home, HOME, clock=lambda: clock[0])
            work = Edge(edge_config(origin), upstream_work, WORK, clock=lambda: clock[0])
            if kind in ("wronghost", "expired"):
                bad = tmp_path / "bad"
                bad.mkdir()
                bad_ca, bad_cert, bad_key = certificates(bad, kind=kind)
                checked = ssl.create_default_context(cafile=str(bad_ca))
                edge_cert, edge_key = bad_cert, bad_key
            else:
                edge_cert, edge_key = cert, key
                checked = verified if kind == "valid" else ssl.create_default_context()
            with tls_server(home, cert, key) as a, tls_server(work, edge_cert, edge_key) as b:
                headers = {
                    "Authorization": "Bearer " + TOKENS["d-device"],
                    "Host": "localhost:8443",
                }
                with httpx.Client(verify=verified, trust_env=False, timeout=2) as client:
                    first = client.get(a + PATH, headers=headers)
                    assert first.status_code == 200 and len(first.json()["nodes"]) == 3
                    assert not [n for n in first.json()["nodes"] if n["site"] == "work"]
                    if kind != "valid":
                        with httpx.Client(verify=checked, trust_env=False, timeout=2) as other:
                            with pytest.raises(httpx.ConnectError):
                                other.get(b + PATH, headers=headers)
                    else:
                        # CASA -> TRABAJO -> CASA; TLS route is explicit, no URL discovery.
                        for edge in (b, a):
                            response = client.get(edge + PATH, headers=headers)
                            assert response.status_code == 200 and response.content == first.content
                            cached = client.get(
                                edge + PATH,
                                headers=headers | {"If-None-Match": response.headers["etag"]},
                            )
                            assert cached.status_code == 304 and not cached.content
                            assert (
                                cached.headers["x-infrabadge-expires"]
                                == response.headers["x-infrabadge-expires"]
                            )
                        # Revocation of only the work edge must not disable home.
                        del core.config.edges["work-edge"]
                        assert client.get(b + PATH, headers=headers).status_code == 401
                        assert client.get(a + PATH, headers=headers).status_code == 200
                        # Old nodes are OFFLINE, never current after a long transport gap.
                        clock[0] = NOW + 601
                        stale = client.get(a + PATH, headers=headers)
                        assert stale.status_code == 200 and stale.json()["status"] == "OFFLINE"
                        assert all(
                            n["cpu"] is None and n["ram"] is None for n in stale.json()["nodes"]
                        )
                        for node in ("a", "b", "c"):
                            core.ingest(node, sample(node=node, at=clock[0]), clock[0])
                        fresh = client.get(a + PATH, headers=headers)
                        assert fresh.status_code == 200
                        assert all(n["valid_until"] > clock[0] for n in fresh.json()["nodes"])
            asyncio.run(upstream_home.aclose())
            asyncio.run(upstream_work.aclose())
    finally:
        store.close()
