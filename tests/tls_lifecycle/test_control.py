"""Control-plane tests replace every system command; no host state is changed."""

import importlib.util
import os
import subprocess
import time
from pathlib import Path

import lifecycle as engine
import pki
import pytest

from tests.tls_lifecycle.test_lifecycle import lab  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools/tls_lifecycle" / filename)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.mark.parametrize("delta,valid", [(120, True), (200, False), (1, False)])
def test_independent_timer_numeric_deadline(monkeypatch, delta, valid):
    cli = module("tls_test_cli", "cli.py")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == "/usr/bin/busctl":
            return f"t {int((time.monotonic() + delta) * 1e6)}".encode()
        return b"active\n"

    monkeypatch.setattr(pki, "command", run)
    host = cli.Host({})
    if valid:
        host.arm()
    else:
        with pytest.raises(ValueError, match="deadline"):
            host.arm()
    assert calls[0][0] == "/usr/bin/systemd-run"
    deadline = next(x for x in calls[0] if x.startswith("--on-boot="))
    assert 110 <= float(deadline.split("=", 1)[1][:-1]) - time.monotonic() <= 125
    assert "--collect" in calls[0]
    assert host.guard_created
    assert not any("stop" in args for args in calls)


def test_never_stop_guard_without_creation(monkeypatch):
    cli = module("tls_test_disarm", "cli.py")
    monkeypatch.setattr(pki, "command", lambda *_: pytest.fail("no owned guard"))
    cli.Host({}).disarm()


def test_prepare_reproducible_inert_units_and_systemd_syntax(tmp_path):
    prepare = module("tls_test_prepare", "prepare.py")
    release = "/opt/infrabadge-tls/releases/" + "a" * 40
    files = prepare.render(release)
    assert len(files) == 9
    assert files == prepare.render(release)
    for name, text in files.items():
        assert "@RELEASE@" not in text
        assert "infrabadge-m32-core.service" not in text
        assert "MemoryMax=" not in text
        (tmp_path / name).write_text(text)
    services = list(tmp_path.glob("*.service")) + list(tmp_path.glob("*.timer"))
    result = subprocess.run(
        ["systemd-analyze", "verify", *map(str, services)],
        capture_output=True,
        text=True,
        env={**os.environ, "SYSTEMD_UNIT_PATH": str(tmp_path) + ":"},
    )
    assert result.returncode == 0, result.stderr
    with pytest.raises(ValueError, match="pinned"):
        prepare.render("/tmp/untrusted")


def test_duplicate_json_and_key_permissions(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "duplicate.json"
    engine.atomic(path, b'{"same":1,"same":2}')
    with pytest.raises(ValueError, match="duplicate"):
        engine.load(path)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="owner_mode"):
        engine.load(path)


@pytest.mark.parametrize("failure", [None, "served_leaf", "probe_drift"])
def test_postcheck_pins_actual_leaf_and_probe(lab, monkeypatch, failure):  # noqa: F811
    import ssl

    config, _, unit, root = lab
    cli = module("tls_test_postcheck", "cli.py")
    probe = root / "probe.json"
    runtime = root / "runtime.json"
    cert, _, ca = engine.paths(config)
    engine.save(probe, {"url": "https://127.0.0.1:8443", "ca_file": str(ca)})
    engine.save(runtime, {"probe_config_sha256": pki.digest(probe)})
    monkeypatch.setattr(cli, "CONFIG", root / "config.json")
    monkeypatch.setattr(cli, "PROBE", probe)
    monkeypatch.setattr(cli, "UNIT", unit)
    monkeypatch.setattr(cli.Host, "check", lambda self: None)
    if failure == "probe_drift":
        engine.save(probe, {"url": "https://elsewhere.invalid:8443", "ca_file": str(ca)})
    calls = []

    class Connection:
        sock = None

        def __init__(self, *args, **kwargs):
            calls.append("connect_created")
            self.sock = self

        def connect(self):
            pass

        def getpeercert(self, binary_form):
            assert binary_form
            return (
                b"old served leaf"
                if failure == "served_leaf"
                else ssl.PEM_cert_to_DER_cert(cert.read_text())
            )

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(cli.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(pki, "command", lambda args, **kwargs: calls.append(args))
    if failure:
        with pytest.raises(ValueError, match="mismatch" if failure == "served_leaf" else "drift"):
            cli.Host(config).probe()
        assert not any(isinstance(x, list) and "/usr/sbin/runuser" in x for x in calls)
    else:
        cli.Host(config).probe()
        assert calls[-1][0] == "/usr/sbin/runuser"


def test_large_private_material_rejected_even_for_metadata(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "too-large.key"
    engine.atomic(path, b"synthetic" * 10000)
    with pytest.raises(ValueError, match="size"):
        pki.private(path, os.getuid(), read=False)
    with pytest.raises(ValueError, match="size"):
        pki.digest(path)
