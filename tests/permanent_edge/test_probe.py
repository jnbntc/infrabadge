"""Real ephemeral loopback TLS probe with a distinct synthetic device identity."""

import asyncio
import hashlib
import http.client
import ssl

import httpx
import ib_edge_lab as lab
import pytest
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.edge import Edge, EdgeConfig
from infrabadge_gateway.distributed.store import Store
from infrabadge_gateway.lab import certificates
from m32_fixtures import NOW, TOKENS, sample
from wire_fixtures import config

from gateway.tests.test_m32_edge import tls_server


@pytest.mark.parametrize(
    "kind",
    [
        "valid",
        "wrong_ca",
        "wrong_host",
        "bad_token",
        "extended_304",
        "near_expiry",
        "changing",
        "core_wrong_ca",
        "core_wrong_host",
        "core_expired",
        "edge_token",
        "collector_token",
        "core_recovery",
        "edge_down",
    ],
)
def test_probe_verified_tls_own_identity_and_no_lifetime_extension(tmp_path, kind, capsys):
    tmp_path.chmod(0o700)
    raw = config().model_dump()
    token = "synthetic-probe-" * 3
    raw["devices"]["probe-home"] = {
        "token_sha256": [hashlib.sha256(token.encode()).hexdigest()],
        "site_ids": ["alpha", "beta"],
        "presentation_v2": True,
    }
    raw["edges"]["edge-a"]["device_ids"].append("probe-home")
    store = Store(tmp_path / "core.db")
    core = Core(type(config()).model_validate(raw), store)
    for node in ("a", "b", "c"):
        core.ingest(node, sample(node=node), NOW)
    tls = tmp_path / "tls"
    tls.mkdir()
    ca, cert, key = certificates(
        tls,
        host="127.0.0.1",
        kind=(
            "wronghost"
            if kind == "core_wrong_host"
            else "expired"
            if kind == "core_expired"
            else "valid"
        ),
    )
    client_ca = ca
    if kind == "core_wrong_ca":
        other = tmp_path / "untrusted-core"
        other.mkdir()
        client_ca, _, _ = certificates(other)
    context = ssl.create_default_context(cafile=str(client_ca))
    front = tmp_path / "front"
    front.mkdir()
    front_ca, front_cert, front_key = certificates(front)
    secret = tmp_path / "probe.token"
    secret.write_text(
        "wrong-token-" * 4
        if kind == "bad_token"
        else TOKENS["collector-a"]
        if kind == "collector_token"
        else token
    )
    secret.chmod(0o600)
    current = [NOW]
    available = [True]
    core_app = create_app(core, clock=lambda: current[0])

    async def core_gate(scope, receive, send):
        if not available[0] and scope["type"] == "http":
            from starlette.responses import Response

            return await Response(status_code=503)(scope, receive, send)
        await core_app(scope, receive, send)

    try:
        with tls_server(core_gate, cert, key) as origin:
            origin = origin.replace("localhost", "127.0.0.1")
            upstream = httpx.AsyncClient(verify=context, trust_env=False, timeout=2)
            edge = Edge(
                EdgeConfig(
                    upstream=origin,
                    device_ids=["probe-home"],
                    ca_file=str(ca),
                    credential_file="/unused",
                    public_hostname="localhost",
                    presentation_v2=True,
                ),
                upstream,
                "x" * 40 if kind == "edge_token" else TOKENS["e-edge"],
                clock=lambda: current[0],
            )

            requests = [0]

            async def altered(scope, receive, send):
                if scope["type"] == "http":
                    requests[0] += 1
                if scope["type"] == "http" and kind == "changing" and requests[0] == 2:
                    current[0] = NOW + 60
                    core.ingest("a", sample(node="a", at=current[0], cpu=25), current[0])

                async def checked(message):
                    if (
                        kind == "extended_304"
                        and message["type"] == "http.response.start"
                        and message["status"] == 304
                    ):
                        message = dict(message)
                        message["headers"] = [
                            (
                                k,
                                str(int(v) + 1).encode()
                                if k.lower() == b"x-infrabadge-expires"
                                else v,
                            )
                            for k, v in message["headers"]
                        ]
                    await send(message)

                await edge(scope, receive, checked)

            edge_cert, edge_key, trusted_ca = front_cert, front_key, front_ca
            if kind in ("wrong_ca", "wrong_host"):
                bad = tmp_path / "bad"
                bad.mkdir()
                other_ca, other_cert, other_key = certificates(
                    bad, kind="wronghost" if kind == "wrong_host" else "valid"
                )
                if kind == "wrong_host":
                    edge_cert, edge_key, trusted_ca = other_cert, other_key, other_ca
                else:
                    trusted_ca = other_ca
            with tls_server(altered, edge_cert, edge_key) as address:
                port = int(address.rsplit(":", 1)[1])
                original = http.client.HTTPSConnection

                class LocalConnection(original):
                    def connect(self):
                        requested = self.port
                        self.port = port
                        try:
                            super().connect()
                        finally:
                            self.port = requested

                settings = {
                    "url": "https://localhost:8443",
                    "ca_file": str(trusted_ca),
                    "token_file": str(secret),
                    "probe_device_id": "probe-home",
                    "minimum_leaf_seconds": 30 * 86400 if kind == "near_expiry" else 0,
                }
                if kind == "core_recovery":
                    available[0] = False
                    with pytest.raises(ValueError):
                        lab.probe(
                            settings, clock=lambda: current[0], connection_factory=LocalConnection
                        )
                    available[0] = True
                    assert lab.probe(
                        settings, clock=lambda: current[0], connection_factory=LocalConnection
                    )["pass"]
                elif kind == "edge_down":

                    class Unavailable(LocalConnection):
                        def connect(self):
                            raise ConnectionRefusedError("synthetic edge offline")

                    with pytest.raises(ConnectionRefusedError):
                        lab.probe(
                            settings, clock=lambda: current[0], connection_factory=Unavailable
                        )
                    assert lab.probe(
                        settings, clock=lambda: current[0], connection_factory=LocalConnection
                    )["pass"]
                elif kind in ("valid", "changing"):
                    result = lab.probe(
                        settings, clock=lambda: current[0], connection_factory=LocalConnection
                    )
                    assert result["pass"] and result["etag_304"] == (kind == "valid")
                    assert result["snapshot_changed"] == (kind == "changing")
                else:
                    with pytest.raises((ValueError, OSError)):
                        lab.probe(
                            settings, clock=lambda: current[0], connection_factory=LocalConnection
                        )
            asyncio.run(upstream.aclose())
    finally:
        store.close()
    output = capsys.readouterr()
    assert token not in output.out + output.err
