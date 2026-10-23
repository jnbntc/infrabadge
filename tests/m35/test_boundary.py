"""Current Core -> Edge -> v1 client, entirely in-process; no listening socket."""

import asyncio
import hashlib
import json

import httpx
from fastapi.testclient import TestClient
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.edge import Edge, EdgeConfig
from infrabadge_gateway.distributed.store import Store
from infrabadge_gateway.models import Snapshot
from m32_fixtures import NOW, TOKENS, configuration, headers, sample


def test_current_two_hop_contract_etag_scope_and_richer_view_gap(tmp_path):
    tmp_path.chmod(0o700)
    store = Store(tmp_path / "synthetic.db")
    core = Core(configuration(), store)
    core.ingest("a", sample(), NOW)
    upstream = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(core, clock=lambda: NOW)),
        base_url="https://central.test:9443",
    )
    cfg = EdgeConfig(
        upstream="https://central.test:9443",
        device_ids=["display-a"],
        ca_file="/synthetic/ca.pem",
        credential_file="/synthetic/edge.token",
        public_hostname="edge.test",
    )
    try:
        with TestClient(
            Edge(cfg, upstream, TOKENS["e-edge"], clock=lambda: NOW),
            base_url="https://edge.test:8443",
        ) as client:
            first = client.get("/api/v1/devices/display-a/status", headers=headers("d-device"))
            assert first.status_code == 200
            snapshot = Snapshot.model_validate_json(first.content)
            assert snapshot.device_id == "display-a" and snapshot.simulated is False
            assert len(first.content) <= 2048 and len(snapshot.alerts) <= 2
            assert first.headers["etag"] == '"' + hashlib.sha256(first.content).hexdigest() + '"'
            assert snapshot.generated_at <= NOW < snapshot.expires_at <= NOW + 180
            assert not {"sites", "nodes", "environment", "views"} & json.loads(first.content).keys()
            cached = client.get(
                "/api/v1/devices/display-a/status",
                headers=headers("d-device", **{"If-None-Match": first.headers["etag"]}),
            )
            assert cached.status_code == 304 and cached.content == b""
            assert (
                client.get("/api/v1/sites/alpha/nodes", headers=headers("r-reader")).status_code
                == 404
            )
            assert (
                client.get(
                    "/api/v2/devices/display-a/views/global", headers=headers("d-device")
                ).status_code
                == 404
            )
            assert (
                client.get(
                    "/api/v1/devices/display-b/status", headers=headers("f-device")
                ).status_code
                == 404
            )
            assert (
                client.post(
                    "/api/v1/collectors/a/metrics", json={}, headers=headers("collector-a")
                ).status_code
                == 404
            )
    finally:
        asyncio.run(upstream.aclose())
        store.close()
