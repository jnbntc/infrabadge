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


@pytest.mark.parametrize("kind", ["missing", "metadata_denied", "unreadable"])
def test_public_runtime_never_inspects_private_key(lab, monkeypatch, kind):  # noqa: F811
    config, _, unit, _ = lab
    key = engine.paths(config)[1]
    if kind == "missing":
        key.unlink()
    elif kind == "unreadable":
        key.chmod(0)
    original_stat, original_lstat = Path.stat, Path.lstat

    def guarded_stat(path, *args, **kwargs):
        if path == key:
            raise AssertionError("public verifier inspected key metadata")
        return original_stat(path, *args, **kwargs)

    def guarded_lstat(path, *args, **kwargs):
        if path == key:
            raise AssertionError("public verifier resolved protected key")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", guarded_stat)
    monkeypatch.setattr(Path, "lstat", guarded_lstat)
    engine.verify_public_runtime(config, unit)


def test_metadata_descriptor_cannot_read_key_content(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    key = tmp_path / "protected.key"
    engine.atomic(key, b"synthetic-secret-not-to-be-read")
    key.chmod(0o400)
    original_open = os.open
    checked = []

    def open_path(path, flags, *args, **kwargs):
        fd = original_open(path, flags, *args, **kwargs)
        if Path(path) == key:
            assert flags & os.O_PATH and flags & os.O_NOFOLLOW
            with pytest.raises(OSError):
                os.read(fd, 1)  # Kernel rejects content access on O_PATH descriptor.
            checked.append(True)
        return fd

    monkeypatch.setattr(os, "open", open_path)
    assert pki.private(key, os.getuid(), read=False) is None
    assert checked == [True]


def test_verifier_sandbox_keeps_all_key_barriers():
    prepare = module("tls_test_barriers", "prepare.py")
    unit = prepare.render("/opt/infrabadge-tls/releases/" + "a" * 40)[
        "infrabadge-tls-verify.service"
    ]
    assert "-/etc/infrabadge-edge-home/server.key" in unit
    assert "-/etc/infrabadge-tls-signer" in unit
    assert "ProtectSystem=strict" in unit and "NoNewPrivileges=true" in unit
    assert "BindReadOnlyPaths=" not in unit and "BindPaths=" not in unit
    assert "CAP_DAC_OVERRIDE" not in unit
