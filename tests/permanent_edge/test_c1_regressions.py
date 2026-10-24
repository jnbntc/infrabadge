"""Regressions from the real A/B pilot; local fixtures, no host administration."""

import errno
import json
import os
import ssl
import subprocess
from types import SimpleNamespace

import ib_edge_lab as lab
import pilot
import pytest
from infrabadge_gateway.lab import certificates

from tests.permanent_edge.test_preparation import TEMPLATES, example
from tests.permanent_edge.test_shared_core import transaction


def test_new_public_release_under_private_umask_preserves_private_tree(tmp_path):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    previous = os.umask(0o077)
    try:
        pilot.public_directory(tmp_path / "release", owner=os.getuid())
        with pytest.raises(ValueError, match="existing_release_directory_permissions"):
            pilot.public_directory(private, owner=os.getuid())
    finally:
        os.umask(previous)
    assert (tmp_path / "release").stat().st_mode & 0o777 == 0o755
    assert private.stat().st_mode & 0o777 == 0o700
    alias = tmp_path / "alias"
    alias.symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        pilot.public_directory(alias, owner=os.getuid())


def test_stage_release_reads_manifest_and_uses_child_only_umask(tmp_path):
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    p = example()
    for name in (
        "gateway/infrabadge_gateway/distributed/cli.py",
        "tools/permanent_edge/pilot.py",
        "gateway/requirements.lock",
        "deploy/m32/native/requirements-runtime.lock",
    ):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source")

    def git(args, **kw):
        return subprocess.CompletedProcess(
            args, 0, stdout=p["release_sha"] if "rev-parse" in args else ""
        )

    (source / "source-manifest.json").write_text(
        json.dumps(pilot.release_manifest(p, source, run=git))
    )
    (source / "source-manifest.json").chmod(0o600)
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout="")

    previous = os.umask(0o077)
    try:
        result = pilot.stage_release(
            p, source, prefix=tmp_path / "edge", owner=os.getuid(), run=run
        )
    finally:
        os.umask(previous)
    assert result["services_changed"] is False
    target = tmp_path / "edge/releases" / p["release_sha"]
    pilot.validate_release(p, target, owner=os.getuid())
    assert (
        target / "gateway/infrabadge_gateway/distributed/cli.py"
    ).stat().st_mode & 0o777 == 0o644
    assert (target / "source-manifest.json").stat().st_mode & 0o777 == 0o600
    assert all(kwargs.get("umask") == 0o022 for _, kwargs in calls[:2])
    assert "--require-hashes" in calls[1][0] and "--only-binary=:all:" in calls[1][0]
    with pytest.raises(ValueError, match="existing_release_preserved"):
        pilot.stage_release(p, source, prefix=tmp_path / "edge", owner=os.getuid(), run=run)
    assert len(calls) == 3


@pytest.mark.parametrize("sources", [["10.23.0.50", "10.23.0.51"], ["10.23.0.50"]])
def test_firewall_sources_are_explicit_hosts_and_position_is_reviewable(sources):
    files = lab.render(
        example() | {"client_ipv4s": sources}, TEMPLATES, "lan", host_accept_position=90
    )
    nft = files["infrabadge-edge-home.nft.proposed"]
    assert "input position 90 iifname" in nft and "10.23.0.0/24" not in nft
    assert all(source + "/32" in nft for source in sources)


@pytest.mark.parametrize(
    "sources",
    [
        [],
        ["10.23.0.50/24"],
        ["10.23.0.50", "10.23.0.50"],
        ["10.24.0.2"],
        ["10.23.0.2"],
        ["10.23.0.51"],
    ],
)
def test_firewall_rejects_broad_duplicate_host_or_unlisted_representative(sources):
    with pytest.raises(ValueError):
        lab.plan(example() | {"client_ipv4s": sources})


def test_readiness_is_bounded_and_tls_failures_are_fatal(tmp_path):
    ca, _, _ = certificates(tmp_path)
    config = {
        "url": "https://localhost:8443",
        "ca_file": str(ca),
        "minimum_leaf_seconds": 1,
        "token_file": str(tmp_path / "MUST_NOT_BE_READ"),
    }
    now = [0.0]
    calls = []
    outcome = [ConnectionRefusedError(errno.ECONNREFUSED, "not ready"), None]

    class Connection:
        sock = SimpleNamespace(getpeercert=lambda: {"notAfter": "Jan 1 00:00:00 2099 GMT"})

        def __init__(self, host, port, **kw):
            calls.append(kw)
            assert kw["context"].check_hostname and kw["context"].verify_mode == ssl.CERT_REQUIRED

        def connect(self):
            error = outcome.pop(0)
            if error:
                raise error

        def close(self):
            pass

    def pause(seconds):
        now[0] += seconds

    result = lab.wait_tls(config, clock=lambda: now[0], pause=pause, connection_factory=Connection)
    assert result["tls_verified"] and result["attempts"] == 2
    outcome[:] = [ssl.SSLCertVerificationError("untrusted"), None]
    with pytest.raises(ssl.SSLCertVerificationError):
        lab.wait_tls(config, clock=lambda: now[0], pause=pause, connection_factory=Connection)
    assert len(outcome) == 1  # No retry of bad CA/SAN/date.
    outcome[:] = [ConnectionRefusedError(errno.ECONNREFUSED, "down")] * 110
    with pytest.raises(TimeoutError, match="readiness_deadline"):
        lab.wait_tls(
            config, timeout=1, clock=lambda: now[0], pause=pause, connection_factory=Connection
        )
    assert all(c["timeout"] <= 1 for c in calls)


def test_readiness_precedes_authenticated_probe_and_watchdog_is_not_rearmed(tmp_path, monkeypatch):
    p, bundle, units, conf, _, _, run, account, calls = transaction(tmp_path, monkeypatch)
    pilot.install_loopback(p, bundle, units, conf, run, account, clock=lambda: 100)
    ready = next(i for i, c in enumerate(calls) if "wait-tls" in c)
    probe = next(i for i, c in enumerate(calls) if "probe" in c)
    assert ready < probe
    assert (
        sum(
            c == ["/usr/bin/systemctl", "start", "infrabadge-edge-home-rollback.timer"]
            for c in calls
        )
        == 1
    )


def test_collector_reload_guard_fails_without_a_safe_window():
    now = [0.0]
    calls = []

    def run(args, **kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="ActiveState=active\nResult=success")

    def pause(seconds):
        now[0] += seconds

    with pytest.raises(ValueError, match="reload_window_unavailable"):
        pilot.collector_reload_window(run, clock=lambda: now[0], pause=pause)
    assert not any("daemon-reload" in c for c in calls)


def test_installed_watchdog_uses_fixed_boot_deadline_before_daemon_reload(tmp_path, monkeypatch):
    p, bundle, units, conf, _, _, run, account, calls = transaction(tmp_path, monkeypatch)
    before = pilot.time.monotonic()
    observed = []

    def watch_reload(args, **kwargs):
        if "daemon-reload" in args:
            text = (units / "infrabadge-edge-home-rollback.timer").read_text()
            observed.append(text)
            assert "OnActiveSec=" not in text
            line = next(x for x in text.splitlines() if x.startswith("OnBootSec="))
            deadline = float(line.removeprefix("OnBootSec=").removesuffix("s"))
            assert before + 1140 <= deadline <= pilot.time.monotonic() + 1140
        return run(args, **kwargs)

    pilot.install_loopback(p, bundle, units, conf, watch_reload, account, clock=lambda: 100)
    assert len(observed) == 1


def test_small_deadline_extension_is_rejected_before_listener(tmp_path, monkeypatch):
    p, bundle, units, conf, _, _, run, account, calls = transaction(
        tmp_path, monkeypatch, "extended_by_reload"
    )
    with pytest.raises(ValueError, match="watchdog_deadline_no_listener"):
        pilot.install_loopback(p, bundle, units, conf, run, account, clock=lambda: 100)
    assert ["/usr/bin/systemctl", "start", "infrabadge-edge-home.service"] not in calls
