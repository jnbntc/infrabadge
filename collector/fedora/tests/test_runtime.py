import json
import os
import ssl
import time
import pytest
from infrabadge_collector import runtime, transport


def private(path, data):
    path.write_text(data)
    path.chmod(0o600)
    return path


def test_private_files_state_corruption_and_symlinks(tmp_path):
    target = private(tmp_path / "secret", "fixture")
    assert runtime.private_bytes(target, 10) == b"fixture"
    target.chmod(0o644)
    with pytest.raises(ValueError):
        runtime.private_bytes(target, 10)
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        runtime.private_bytes(link, 10)
    assert runtime.load_baseline(target) is None
    baseline = {"ticks": [1] * 8, "logical_cpus": 2, "uptime": 30.0}
    runtime.save_baseline(target, baseline)
    assert runtime.load_baseline(target) == baseline
    private(target, '{"ticks":[true],"logical_cpus":2,"uptime":30}')
    assert runtime.load_baseline(target) is None


def test_config_requires_verified_origin_and_logical_labels(tmp_path):
    value = {"node_id": "workstation", "gateway_url": "https://localhost:8443", "ca_file": "/tmp/ca.pem",
             "mount_path": "/var/home", "mount_id": "HOME", "state_file": "/tmp/cpu.json",
             "interval_seconds": 60, "timeout_seconds": 5}
    path = private(tmp_path / "config", json.dumps(value))
    assert runtime.load_config(path) == value
    for change in ({"gateway_url": "http://localhost"}, {"gateway_url": "https://token@localhost"},
                   {"gateway_url": "https://localhost/?secret=x"}, {"mount_id": "/personal/path"},
                   {"interval_seconds": True}, {"unknown": 1}):
        private(path, json.dumps(dict(value, **change)))
        with pytest.raises(ValueError):
            runtime.load_config(path)


def test_root_and_container_guard(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(ValueError, match="non_root"):
        runtime.require_host()
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setenv("container", "synthetic")
    with pytest.raises(ValueError, match="namespace"):
        runtime.require_host()


def test_deadline_is_process_local_and_restored():
    import signal
    original = signal.getsignal(signal.SIGALRM)
    with pytest.raises(TimeoutError):
        with transport.deadline(0.01):
            time.sleep(1)
    assert signal.getsignal(signal.SIGALRM) == original


@pytest.mark.parametrize("status", [202, 301, 401, 500])
def test_transport_no_redirect_proxy_or_response_logging(tmp_path, monkeypatch, status):
    token = private(tmp_path / "token", "synthetic-token-" + "x" * 32)
    observed = []
    class Response:
        def read(self, size):
            assert size == 1025
            return b'{"accepted":true}'
    Response.status = status
    class Connection:
        def __init__(self, host, port, timeout, context):
            assert host == "localhost" and port == 8443 and timeout == 1
            assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        def request(self, method, path, body, headers):
            observed.append((method, path))
            assert headers["Authorization"].startswith("Bearer synthetic-token-")
        def getresponse(self):
            return Response()
        def close(self):
            observed.append("closed")
    monkeypatch.setattr(transport.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(transport.ssl, "create_default_context", lambda **kwargs: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    config = {"gateway_url": "https://localhost:8443", "ca_file": "unused", "timeout_seconds": 1, "node_id": "workstation"}
    if status == 202:
        transport.submit(config, token, {"node_id": "workstation"})
    else:
        with pytest.raises(ValueError, match="gateway_rejected"):
            transport.submit(config, token, {"node_id": "workstation"})
    assert observed == [("POST", "/api/v1/collectors/workstation/metrics"), "closed"]
