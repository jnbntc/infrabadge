"""Control-plane tests replace every system command; no host state is changed."""

import importlib.util
import os
import subprocess
import time
from pathlib import Path

import lifecycle as engine
import pki
import pytest

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
    assert "--on-active=120s" in calls[0]
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
