"""Permanent CASA ownership, boot reconstruction and fail-closed publication tests."""

import copy
import errno
import hashlib
import json
import os
import ssl
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import permanent
import pilot
import pytest
import retirement
import rollback
import tls_check
from infrabadge_gateway.lab import certificates

from tests.permanent_edge.test_preparation import example


def fixture():
    chain = {"chain": {"family": "inet", "table": "infrabadge_host", "name": "input", "handle": 2}}
    drop = {
        "rule": {
            "family": "inet",
            "table": "infrabadge_host",
            "chain": "input",
            "handle": 9,
            "expr": [{"counter": {"packets": 1, "bytes": 7}}, {"drop": None}],
        }
    }
    table = [{"table": {"family": "inet", "name": permanent.TABLE, "handle": 50}}]
    rule = {
        "family": "inet",
        "table": "infrabadge_host",
        "chain": "input",
        "handle": 51,
        "comment": permanent.COMMENT,
        "expr": [{"accept": None}],
    }
    base = {"nftables": [chain, drop]}
    applied = {"nftables": table + [chain, {"rule": rule}, drop]}
    value = {
        "schema_version": 1,
        "plan": example() | {"edge_hostname": example()["lan_ipv4"]},
        "baseline_chain_sha256": rollback.table_digest(base),
        "expected_table_sha256": rollback.table_digest({"nftables": table}),
        "expected_rule_sha256": rollback.table_digest(rule),
        "units_sha256": {p: "a" * 64 for p in permanent.UNIT_PATHS},
    }
    return value, base, applied


class Kernel:
    def __init__(self):
        self.value, self.base, self.applied = fixture()
        self.data = copy.deepcopy(self.base)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        assert args[:1] == ["/usr/sbin/nft"]
        if "-j" in args:
            return SimpleNamespace(stdout=json.dumps(self.data))
        batch = kwargs["input"]
        assert "flush" not in batch
        if "--check" not in args:
            if batch.startswith("delete rule"):
                assert "handle 51\ndelete table inet infrabadge_edge_home\n" in batch
                self.data = copy.deepcopy(self.base)
            else:
                assert "position 9" in batch
                assert "10.23.0.50/32" in batch
                self.data = copy.deepcopy(self.applied)
        return SimpleNamespace(stdout="")


@pytest.fixture
def private_as_test_uid(monkeypatch):
    original = rollback.private
    monkeypatch.setattr(rollback, "private", lambda p: original(p, owner=os.getuid()))


def test_boot_reconstruction_idempotence_and_atomic_owned_removal(tmp_path, private_as_test_uid):
    kernel = Kernel()
    state = tmp_path / "firewall.json"
    assert permanent.start_firewall(kernel.value, state, "boot", kernel)["objects"] == 2
    mutations = len([c for c, _ in kernel.calls if "--file" in c and "--check" not in c])
    assert permanent.start_firewall(kernel.value, state, "boot", kernel)["already_active"]
    assert len([c for c, _ in kernel.calls if "--file" in c and "--check" not in c]) == mutations
    assert permanent.stop_firewall(kernel.value, state, "boot", kernel)["removed"]
    assert kernel.data == kernel.base and not state.exists()
    assert permanent.stop_firewall(kernel.value, state, "boot", kernel)["already_absent"]
    # Fresh boot, same persisted config, new runtime and rebuilt objects.
    assert permanent.start_firewall(kernel.value, state, "next-boot", kernel)["applied"]
    with pytest.raises(ValueError, match="state_drift"):
        permanent.stop_firewall(kernel.value, state, "wrong-boot", kernel)


@pytest.mark.parametrize("kind", ["table", "rule", "base"])
def test_drift_never_deletes_or_accepts_partial_objects(tmp_path, private_as_test_uid, kind):
    kernel = Kernel()
    state = tmp_path / "firewall.json"
    permanent.start_firewall(kernel.value, state, "boot", kernel)
    if kind == "table":
        kernel.data["nftables"][0]["table"]["name"] = "other_owner"
    elif kind == "rule":
        kernel.data["nftables"][2]["rule"]["expr"] = [{"drop": None}]
    else:
        kernel.data["nftables"][-1]["rule"]["comment"] = "changed-base"
    before = copy.deepcopy(kernel.data)
    with pytest.raises(ValueError):
        permanent.stop_firewall(kernel.value, state, "boot", kernel)
    assert kernel.data == before and state.exists()


def test_publication_failure_removes_exact_new_objects(tmp_path, monkeypatch):
    kernel = Kernel()
    state = tmp_path / "firewall.json"

    def fail(*args):
        raise OSError("synthetic full filesystem")

    monkeypatch.setattr(permanent, "atomic_json", fail)
    with pytest.raises(OSError):
        permanent.start_firewall(kernel.value, state, "boot", kernel)
    assert kernel.data == kernel.base and not state.exists()
    mutations = [
        kw["input"] for args, kw in kernel.calls if "--file" in args and "--check" not in args
    ]
    assert len(mutations) == 2 and mutations[-1].count("delete ") == 2


def test_preexisting_or_changed_base_is_not_adopted(tmp_path):
    kernel = Kernel()
    kernel.data = kernel.applied
    with pytest.raises(ValueError, match="unowned_firewall_collision"):
        permanent.start_firewall(kernel.value, tmp_path / "state", "boot", kernel)
    kernel.data = copy.deepcopy(kernel.base)
    kernel.data["nftables"][-1]["rule"]["comment"] = "changed"
    with pytest.raises(ValueError, match="host_firewall_drift"):
        permanent.start_firewall(kernel.value, tmp_path / "state", "boot", kernel)
    assert not any("--file" in args for args, _ in kernel.calls)


def test_unit_ownership_refuses_drift_symlinks_and_other_services(tmp_path):
    value, _, _ = fixture()
    for name in permanent.UNIT_PATHS:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("synthetic root-owned unit")
        value["units_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    permanent.verify_units(value, tmp_path, owner=os.getuid())
    path = tmp_path / (permanent.STEM + ".service")
    path.write_text("drift")
    with pytest.raises(ValueError, match="unit_drift"):
        permanent.verify_units(value, tmp_path, owner=os.getuid())
    path.unlink()
    path.symlink_to(tmp_path / (permanent.STEM + "-probe.service"))
    with pytest.raises(ValueError, match="unit_symlink"):
        permanent.verify_units(value, tmp_path, owner=os.getuid())
    value["units_sha256"]["infrabadge-m32-core.service"] = "a" * 64
    with pytest.raises(ValueError, match="unit_set"):
        permanent.contract(value)


def test_permanent_units_and_manifest_cover_boot_and_tls_without_core_control(tmp_path):
    files = permanent.render(example())
    firewall = files[permanent.STEM + "-firewall.service"]
    dropin = files[permanent.STEM + ".service.d/10-permanent.conf"]
    assert "After=network-online.target infrabadge-firewall.service" in firewall
    assert "Requires=infrabadge-firewall.service" not in firewall
    assert "RuntimeDirectoryMode=0700" in firewall and "CAP_NET_ADMIN" in firewall
    assert "Requires=infrabadge-edge-home-firewall.service" in dropin
    assert "tls_check.py ready" in dropin
    assert all("Requires=infrabadge-m32-core" not in text for text in files.values())
    assert "Persistent=true" in files[permanent.STEM + "-tls-check.timer"]
    release = tmp_path / "release"
    (release / "venv/bin").mkdir(parents=True)
    (release / "venv/bin/python").symlink_to(sys.executable)
    paths = []
    for name, text in files.items():
        if not name.endswith(".service") and not name.endswith(".timer"):
            continue
        path = tmp_path / name
        path.write_text(
            text.replace("/opt/infrabadge-edges/releases/" + example()["release_sha"], str(release))
        )
        paths.append(str(path))
    result = subprocess.run(
        ["systemd-analyze", "verify", "--man=no", *paths], capture_output=True, timeout=15
    )
    assert result.returncode == 0, result.stderr.decode()
    names = pilot.release_files(pilot.lab.ROOT)
    assert all(
        "deploy/permanent_edge/persistent/" + name in names
        for name in (
            "10-permanent.conf.in",
            permanent.STEM + "-firewall.service.in",
            permanent.STEM + "-tls-check.service.in",
            permanent.STEM + "-tls-check.timer.in",
        )
    )


@pytest.mark.parametrize(
    "seconds,status",
    [
        (11 * 86400, "ok"),
        (10 * 86400, "warning"),
        (7 * 86400, "critical"),
        (0, "expired"),
        (-1, "expired"),
    ],
)
def test_expiry_thresholds(seconds, status):
    assert tls_check.expiry_status(seconds) == status


def test_expiry_monitor_verifies_real_chain_san_and_does_not_read_tokens(tmp_path):
    plan = example() | {"edge_hostname": example()["lan_ipv4"]}
    ca, _, _ = certificates(tmp_path, host=plan["lan_ipv4"])
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "plan.json").chmod(0o600)
    for name in ("edge-ca.pem", "core-ca.pem"):
        (tmp_path / name).write_bytes(ca.read_bytes())
    result = tls_check.certificates(tmp_path, plan["lan_ipv4"])
    assert result["status"] == "critical" and result["remote_notification_configured"] is False
    with pytest.raises(ValueError, match="approved_address"):
        tls_check.certificates(tmp_path, "10.23.0.99")
    # Another approved fixture IP with the original leaf must fail real SAN verification.
    plan["lan_ipv4"] = "10.23.0.3"
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    with pytest.raises(subprocess.CalledProcessError):
        tls_check.certificates(tmp_path, plan["lan_ipv4"])


def test_companion_manifest_hashes_match_rendered_units():
    value, base, applied = fixture()
    table, _, rules = permanent.objects(applied)
    files, manifest = permanent.prepare_companions(value["plan"], table, rules[0], base)
    assert set(files) == permanent.UNIT_PATHS
    assert manifest["units_sha256"] == {
        name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()
    }
    assert manifest["expected_table_sha256"] == value["expected_table_sha256"]


def test_core_readiness_is_tls_only_bounded_and_ca_failure_is_fatal(tmp_path):
    ca, _, _ = certificates(tmp_path)
    now = [0.0]
    outcomes = [ConnectionRefusedError(errno.ECONNREFUSED, "not yet"), None]
    seen = []

    class Connection:
        def __init__(self, host, port, **kwargs):
            assert (host, port) == ("127.0.0.1", 9443)
            assert kwargs["context"].check_hostname
            assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED
            seen.append(kwargs)

        def connect(self):
            outcome = outcomes.pop(0)
            if outcome:
                raise outcome

        def close(self):
            pass

    def pause(seconds):
        now[0] += seconds

    def run(args, **kw):
        assert args[0] == "/usr/bin/timedatectl"
        return SimpleNamespace(stdout="yes\n")

    result = tls_check.core_ready(ca, run, Connection, lambda: now[0], pause)
    assert result["tls_verified"] and not result["http_sent"] and len(seen) == 2
    outcomes[:] = [ssl.SSLCertVerificationError("bad CA"), None]
    with pytest.raises(ssl.SSLCertVerificationError):
        tls_check.core_ready(ca, run, Connection, lambda: now[0], pause)
    assert outcomes == [None]
    outcomes[:] = [ConnectionRefusedError(errno.ECONNREFUSED, "down")] * 20
    with pytest.raises(TimeoutError, match="readiness_deadline"):
        tls_check.core_ready(ca, run, Connection, lambda: now[0], pause, timeout=1)
    assert now[0] < 2


def test_cli_loads_in_isolated_python_and_never_needs_root_for_help():
    for file in (permanent.__file__, tls_check.__file__):
        result = subprocess.run(
            [sys.executable, "-I", "-B", file, "--help"], capture_output=True, timeout=5
        )
        assert result.returncode == 0, result.stderr.decode()


def test_full_retirement_archives_only_recorded_paths_and_preserves_external_targets(tmp_path):
    root = tmp_path / "host"
    config = root / "etc/infrabadge-edge-home"
    config.mkdir(parents=True, mode=0o700)
    (config / "probe.token").write_text("synthetic private token")
    external = tmp_path / "must-not-touch"
    external.write_text("existing Core")
    release = root / ("opt/infrabadge-edges/releases/" + "a" * 40)
    release.mkdir(parents=True)
    (release / "interpreter-link").symlink_to(external)
    value = retirement.record("a" * 40, 500, 500, True, root)
    retirement.verify(value, root)
    (config / "probe.token").write_text("drift")
    with pytest.raises(ValueError, match="file_drift"):
        retirement.archive_files(value, tmp_path / "rejected-archive", root)
    assert config.exists() and not (tmp_path / "rejected-archive").exists()
    (config / "probe.token").write_text("synthetic private token")
    result = retirement.archive_files(value, tmp_path / "archive", root)
    assert not config.exists() and not release.exists()
    assert result["credentials_deleted"] is False
    assert (
        tmp_path / "archive/etc/infrabadge-edge-home/probe.token"
    ).read_text() == "synthetic private token"
    assert external.read_text() == "existing Core"
    value["files"]["/etc/infrabadge/m32"] = {}
    with pytest.raises(ValueError, match="retirement_scope"):
        retirement.verify(value, root)


def test_failed_archive_restores_already_moved_owned_files(tmp_path, monkeypatch):
    root = tmp_path / "host"
    config = root / "etc/infrabadge-edge-home"
    config.mkdir(parents=True, mode=0o700)
    (config / "probe.token").write_text("synthetic token")
    release = root / ("opt/infrabadge-edges/releases/" + "a" * 40)
    release.mkdir(parents=True)
    (release / "app.py").write_text("synthetic pinned source")
    value = retirement.record("a" * 40, 500, 500, True, root)
    original = Path.rename
    raised = []

    def rename(path, destination):
        if path == release and not raised:
            raised.append(True)
            raise OSError("synthetic archive error")
        return original(path, destination)

    monkeypatch.setattr(Path, "rename", rename)
    with pytest.raises(OSError):
        retirement.archive_files(value, tmp_path / "archive", root)
    retirement.verify(value, root)
    assert (config / "probe.token").read_text() == "synthetic token"


@pytest.mark.parametrize("fail", [False, True])
def test_runtime_tmpfs_archive_and_recovery(tmp_path, monkeypatch, fail):
    root = tmp_path / "host"
    config = root / "etc/infrabadge-edge-home"
    config.mkdir(parents=True, mode=0o700)
    (config / "probe.token").write_text("synthetic token")
    runtime = root / "run/infrabadge-edge-home"
    runtime.mkdir(parents=True, mode=0o700)
    (runtime / "a.json").write_text("owned state")
    (runtime / "b.json").write_text("owned plan")
    value = retirement.record("a" * 40, 500, 500, True, root)
    original_stat, original_unlink = Path.lstat, Path.unlink
    raised = []

    def lstat(path, *args, **kwargs):
        info = original_stat(path, *args, **kwargs)
        if path == runtime:
            return SimpleNamespace(
                st_dev=info.st_dev + 1, st_mode=info.st_mode, st_uid=info.st_uid, st_gid=info.st_gid
            )
        return info

    def unlink(path, *args, **kwargs):
        if fail and path == runtime / "b.json" and not raised:
            raised.append(True)
            raise OSError("synthetic partial tmpfs removal failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "unlink", unlink)
    if fail:
        with pytest.raises(OSError):
            retirement.archive_files(value, tmp_path / "archive", root)
        retirement.verify(value, root)
    else:
        retirement.archive_files(value, tmp_path / "archive", root)
        assert not runtime.exists() and not config.exists()
    assert (tmp_path / "archive/run/infrabadge-edge-home/a.json").read_text() == "owned state"
