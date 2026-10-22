"""Regression of deployed native adaptations using synthetic data, never real hosts."""

import http.client
import json
import os
import signal
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

import core_sockets
import pytest
from check_native import check
from fastapi.testclient import TestClient
from infrabadge_collector.runtime import private_bytes
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.store import Store
from infrabadge_gateway.lab import certificates
from m32_fixtures import NOW, configuration, headers, sample

ROOT = Path(__file__).resolve().parents[2]


def test_native_templates_and_runtime_subset_remain_inert():
    assert check() == dict(
        status="PASS",
        runtime_packages=17,
        templates=4,
        systemd_syntax_verified=False,
        installed=False,
        hosts_contacted=False,
    )


def test_staged_credential_preserves_strict_reader_and_source_permissions(tmp_path):
    delivered = tmp_path / "delivered"
    delivered.write_text("c" * 40)
    delivered.chmod(0o440)
    with pytest.raises(ValueError):
        private_bytes(delivered, 128)
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    owned = runtime / "collector.token"
    subprocess.run(["/usr/bin/install", "-m", "0600", str(delivered), str(owned)], check=True)
    assert private_bytes(owned, 128) == b"c" * 40
    assert owned.stat().st_uid == os.getuid()
    assert owned.stat().st_mode & 0o777 == 0o600
    assert delivered.stat().st_mode & 0o777 == 0o440


def test_restart_and_early_timer_delivery_rejects_without_changing_watermark(tmp_path):
    """Expected429 reproduces timing policy, not proof of the historical HTTP cause."""
    tmp_path.chmod(0o700)
    cfg = configuration()
    cfg.nodes["a"].health_policy.min_interval_seconds = 15
    store = Store(tmp_path / "core.db")
    core = Core(cfg, store)
    core.ingest("a", sample(), NOW)
    store.close()
    store = Store(tmp_path / "core.db")
    try:
        restarted = Core(cfg, store)
        now = [NOW + 9]
        with TestClient(create_app(restarted, clock=lambda: now[0])) as client:
            reply = client.post(
                "/api/v1/collectors/a/metrics",
                json=sample(at=now[0]).model_dump(),
                headers=headers("collector-a"),
            )
            assert reply.status_code == 429
            assert store.db.execute("SELECT collected,received FROM latest").fetchone() == (
                NOW,
                NOW,
            )
            assert restarted.inventory("alpha", now[0])["nodes"][0]["freshness"] == "restored"
            now[0] = NOW + 40
            reply = client.post(
                "/api/v1/collectors/a/metrics",
                json=sample(at=now[0]).model_dump(),
                headers=headers("collector-a"),
            )
            assert reply.status_code == 202
            assert restarted.inventory("alpha", now[0])["nodes"][0]["status"] == "HEALTHY"
    finally:
        store.close()


@pytest.mark.parametrize("failure", ["pid", "count", "family", "type", "accept", "address"])
def test_activation_rejects_wrong_descriptors_before_any_store(monkeypatch, failure):
    made = []

    class Channel:
        family = socket.AF_UNIX if failure == "family" else socket.AF_INET

        def __init__(self, fileno):
            self.fd, self.closed = fileno, False
            made.append(self)

        def getsockopt(self, level, option):
            if option == socket.SO_TYPE:
                return socket.SOCK_DGRAM if failure == "type" else socket.SOCK_STREAM
            return 0 if failure == "accept" else 1

        def set_inheritable(self, value):
            assert value is False

        def getsockname(self):
            return (
                "127.0.0.1"
                if self.fd == 3
                else "127.0.0.3"
                if failure == "address"
                else "127.0.0.2",
                9443,
            )

        def close(self):
            self.closed = True

    monkeypatch.setenv("LISTEN_PID", "0" if failure == "pid" else str(os.getpid()))
    monkeypatch.setenv("LISTEN_FDS", "1" if failure == "count" else "2")
    monkeypatch.setattr(core_sockets.socket, "socket", Channel)
    with pytest.raises(ValueError):
        core_sockets.inherited_sockets(["127.0.0.1", "127.0.0.2"], 9443)
    assert all(x.closed for x in made)


@pytest.mark.parametrize(
    "addresses",
    [
        ["0.0.0.0", "127.0.0.2"],
        ["127.0.0.1", "224.0.0.1"],
        ["127.0.0.1", "127.0.0.1"],
        ["127.0.0.1"],
    ],
)
def test_adapter_invalid_listeners_never_create_database(tmp_path, monkeypatch, capsys, addresses):
    database = tmp_path / "must-not-exist.db"
    args = [
        "adapter",
        "--config",
        str(tmp_path / "private.json"),
        "--database",
        str(database),
        "--cert",
        str(tmp_path / "cert"),
        "--key",
        str(tmp_path / "key"),
    ]
    for address in addresses:
        args += ["--listener", address]
    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(core_sockets.os, "geteuid", lambda: 1000)
    assert core_sockets.main() == 1 and not database.exists()
    assert json.loads(capsys.readouterr().out)["event"] == "unavailable"


def test_two_inherited_tls_sockets_share_one_store_and_identity_scopes(tmp_path):
    """Actual loopback TLS and FDs, synthetic inventory. No Tailscale/firewall claim."""
    tmp_path.chmod(0o700)
    ca, cert, key = certificates(tmp_path)
    config = tmp_path / "core.json"
    config.write_text(configuration().model_dump_json())
    config.chmod(0o600)
    database = tmp_path / "core.db"
    harness = """import os,socket,sys
from core_sockets import main
channels=[]
port=0
for address in ("127.0.0.1","127.0.0.2"):
 s=socket.socket();s.bind((address,port));port=s.getsockname()[1];s.listen(16);channels.append(s)
assert [s.fileno() for s in channels]==[3,4]
os.environ["LISTEN_PID"]=str(os.getpid());os.environ["LISTEN_FDS"]="2"
sys.argv=["adapter",*sys.argv[1:],"--port",str(port)]
print(port,flush=True)
raise SystemExit(main())
"""
    env = os.environ | {
        "PYTHONPATH": os.pathsep.join([str(ROOT / "gateway"), str(ROOT / "deploy/m32/native")]),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            harness,
            "--config",
            str(config),
            "--database",
            str(database),
            "--cert",
            str(cert),
            "--key",
            str(key),
            "--listener",
            "127.0.0.1",
            "--listener",
            "127.0.0.2",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port = int(process.stdout.readline().strip())
        context = ssl.create_default_context(cafile=str(ca))

        def request(address, method, path, auth, body=b""):
            with socket.create_connection((address, port), timeout=5) as channel:
                with context.wrap_socket(channel, server_hostname="localhost") as channel:
                    fields = {
                        "Host": "localhost",
                        "Connection": "close",
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                    } | auth
                    raw = (
                        f"{method} {path} HTTP/1.1\r\n"
                        + "".join(f"{k}: {v}\r\n" for k, v in fields.items())
                        + "\r\n"
                    )
                    channel.sendall(raw.encode() + body)
                    response = http.client.HTTPResponse(channel)
                    response.begin()
                    return response.status, response.read()

        at = int(time.time())
        payload = sample().model_dump() | {"collected_at": at, "uptime_seconds": 1000.0}
        assert (
            request(
                "127.0.0.1",
                "POST",
                "/api/v1/collectors/a/metrics",
                headers("collector-a"),
                json.dumps(payload).encode(),
            )[0]
            == 202
        )
        for address in ("127.0.0.1", "127.0.0.2"):
            status, body = request(address, "GET", "/api/v1/sites/alpha/nodes", headers("r-reader"))
            assert status == 200 and json.loads(body)["nodes"][0]["status"] == "HEALTHY"
        assert (
            request("127.0.0.2", "GET", "/api/v1/sites/beta/nodes", headers("r-reader"))[0] == 403
        )
        with pytest.raises((OSError, ValueError)):
            Store(database)
    finally:
        process.terminate()
        process.communicate(timeout=8)
    assert process.returncode in (0, -signal.SIGTERM)  # Uvicorn re-raises the captured signal.
    store = Store(database)
    try:
        assert store.db.execute("SELECT count(*) FROM latest").fetchone() == (1,)
        assert (
            Core(configuration(), store).inventory("alpha", int(time.time()))["nodes"][0][
                "freshness"
            ]
            == "restored"
        )
    finally:
        store.close()
