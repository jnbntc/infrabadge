"""CASA colocated Core: temp filesystem, mocked administration, no real services."""

import json
import os
import subprocess
import time
from types import SimpleNamespace

import ib_edge_lab as lab
import pilot
import pytest
import rollback
from infrabadge_gateway.lab import certificates

from tests.permanent_edge.test_preparation import example, rollback_plan


@pytest.mark.parametrize(
    "changes",
    [
        {"core_ipv4": "100.64.0.10"},
        {"schema_version": 1},
        {"service_user": "infrabadge"},
        {"service_user": "ibcollector"},
        {"device_ids": ["probe-home"]},
        {"device_ids": ["badge-demo", "badge-demo"]},
        {"probe_device_id": "badge-demo"},
    ],
)
def test_home_refuses_remote_core_shared_accounts_or_shared_probe(changes):
    with pytest.raises(ValueError):
        lab.plan(example() | changes)


def test_prepare_defaults_to_loopback_and_separate_config_without_secrets(tmp_path):
    tmp_path.chmod(0o700)
    p = example()
    target = tmp_path / "bundle"
    result = pilot.prepare(p, target)
    assert result["files"] == 9 and result["installed"] is False
    service = (target / "infrabadge-edge-home.service").read_text()
    assert "--bind 127.0.0.1 --port 8443" in service
    assert "After=infrabadge-m32-core.socket" in service
    assert "Requires=infrabadge-m32-core" not in service
    assert "BindsTo=" not in service and "PartOf=" not in service
    assert "InaccessiblePaths=-/etc/infrabadge -/var/lib/infrabadge" in service
    config = json.loads((target / "edge.json").read_text())
    assert config["upstream"] == "https://127.0.0.1:9443"
    assert config["device_ids"] == p["device_ids"] and config["public_hostname"] == "127.0.0.1"
    assert "/etc/infrabadge-edge-home/" in config["ca_file"]
    assert "token_sha256" not in json.dumps(config)
    assert all(f.stat().st_mode & 0o077 == 0 for f in target.iterdir())
    proposed = lab.render(p, lab.ROOT / "deploy/permanent_edge", "lan")
    assert "--bind 10.23.0.2 --port 8443" in proposed["infrabadge-edge-home.service"]
    nft = proposed["infrabadge-edge-home.nft.proposed"]
    assert "insert rule inet infrabadge_host input" in nft
    assert 'comment "infrabadge-edge-home-allow8443"' in nft
    assert 'iifname "lo" ip daddr 10.23.0.2 tcp dport 8443 accept' in nft
    assert "9443" not in nft and "flush " not in nft and "tailscale0" not in nft


def test_install_gate_rejects_nas_even_if_root(tmp_path, monkeypatch, capsys):
    tmp_path.chmod(0o700)
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(example()))
    p.chmod(0o600)
    monkeypatch.setattr(
        "sys.argv",
        [
            "pilot",
            "install-loopback",
            "--plan",
            str(p),
            "--directory",
            str(tmp_path),
            "--execute-authorized-loopback-install",
        ],
    )
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(pilot.socket, "gethostname", lambda: "nas-01")
    assert pilot.main() == 1
    assert list(tmp_path.iterdir()) == [p]
    assert "nas-01" not in capsys.readouterr().out


def transaction(tmp_path, monkeypatch, kind="success"):
    tmp_path.chmod(0o700)
    p = example()
    bundle = tmp_path / "bundle"
    pilot.prepare(p, bundle)
    for name in pilot.MATERIALS:
        f = bundle / name
        f.write_text("synthetic-only-material")
        f.chmod(0o600)
    unitroot = tmp_path / "units"
    unitroot.mkdir()
    configroot = tmp_path / "etc"
    configroot.mkdir()
    core = tmp_path / "core.db"
    core.write_text("CORE SENTINEL")
    coreunit = unitroot / "infrabadge-m32-core.service"
    coreunit.write_text("CORE UNIT SENTINEL")
    monkeypatch.setattr(pilot, "validate_materials", lambda *args: None)
    calls = []
    created = [False]
    shown = [0]

    def account(name):
        if not created[0]:
            raise KeyError(name)
        return SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())

    def run(args, **kwargs):
        calls.append(args)
        text = ""
        if args[0].endswith("useradd"):
            created[0] = True
        elif args[0].endswith("nft"):
            text = '{"nftables":[]}'
        elif args[0].endswith("busctl"):
            text = "t " + str(
                int((time.monotonic() + (3000 if kind == "late_watchdog" else 1140)) * 1e6)
            )
        elif args[0].endswith("runuser"):
            if kind == "probe_failure":
                raise subprocess.CalledProcessError(1, args)
        elif "is-active" in args:
            text = "inactive" if kind == "unarmed" else "active"
        elif "show" in args:
            if "infrabadge-m32-core.service" in args:
                shown[0] += 1
                text = "ActiveState=active\nMainPID=" + (
                    "999" if kind == "core_drift" and shown[0] > 1 else "42"
                )
            else:
                text = "ActiveState=active\nMainPID=0"
        return subprocess.CompletedProcess(args, 0, stdout=text)

    return p, bundle, unitroot, configroot, core, coreunit, run, account, calls


@pytest.mark.parametrize(
    "kind",
    [
        "success",
        "probe_failure",
        "unarmed",
        "late_watchdog",
        "core_drift",
        "collision",
        "bundle_drift",
    ],
)
def test_loopback_install_and_failures_never_change_core_or_firewall(tmp_path, monkeypatch, kind):
    p, bundle, units, conf, db, coreunit, run, account, calls = transaction(
        tmp_path, monkeypatch, kind
    )
    if kind == "collision":
        (units / "infrabadge-edge-home.service").write_text("EXISTING")
    if kind == "bundle_drift":
        f = bundle / "edge.json"
        f.write_text("{}")
    if kind == "success":
        result = pilot.install_loopback(p, bundle, units, conf, run, account, clock=lambda: 100)
        assert result["watchdog_armed"] and result["firewall_unchanged"] and not result["enabled"]
        start = calls.index(["/usr/bin/systemctl", "start", "infrabadge-edge-home.service"])
        arm = calls.index(["/usr/bin/systemctl", "start", "infrabadge-edge-home-rollback.timer"])
        assert arm < start and any(c[0].endswith("busctl") for c in calls[arm:start])
        state = json.loads((conf / "trial-state/rollback.json").read_text())
        assert state["table_sha256"] is None and state["deadline_boottime"] == 1240
    else:
        with pytest.raises((ValueError, subprocess.CalledProcessError)):
            pilot.install_loopback(p, bundle, units, conf, run, account, clock=lambda: 100)
        if kind in ("unarmed", "late_watchdog", "collision", "bundle_drift"):
            assert ["/usr/bin/systemctl", "start", "infrabadge-edge-home.service"] not in calls
        if kind in ("collision", "bundle_drift"):
            assert not calls
    assert db.read_text() == "CORE SENTINEL" and coreunit.read_text() == "CORE UNIT SENTINEL"
    assert not any("enable" in c or "restart" in c or "reboot" in c for c in calls)
    assert not any(
        c[0].endswith("nft") and any(x in c for x in ("add", "insert", "delete", "flush", "-f"))
        for c in calls
    )
    assert not any(
        any(u in c for u in pilot.CORE_UNITS) and any(x in c for x in ("start", "stop", "restart"))
        for c in calls
    )


def test_loopback_rollback_uses_no_firewall_or_core_commands(tmp_path):
    p, _ = rollback_plan(tmp_path)
    p["table_sha256"] = None
    calls = []

    def run(args, **kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    result = rollback.execute(p, "c" * 64, 1240, unit_root=tmp_path, run=run)
    assert result["listener_stopped"] and not result["firewall_changed"] and len(calls) == 1
    assert "infrabadge-m32-core.service" not in calls[0]


def host_rule():
    return {
        "family": "inet",
        "table": "infrabadge_host",
        "chain": "input",
        "handle": 90,
        "comment": "infrabadge-edge-home-allow8443",
        "expr": [
            {
                "match": {
                    "op": "==",
                    "left": {"payload": {"protocol": "tcp", "field": "dport"}},
                    "right": 8443,
                }
            },
            {"accept": None},
        ],
    }


@pytest.mark.parametrize("drift", [False, True])
def test_lan_rollback_deletes_only_owned_exception_and_table(tmp_path, drift):
    p, table = rollback_plan(tmp_path)
    rule = host_rule()
    p["host_accept_rule"] = {"handle": 90, "sha256": rollback.table_digest(rule)}
    if drift:
        rule["expr"][0]["match"]["right"] = 9443
    calls = []

    def run(args, **kw):
        calls.append(args)
        data = {"nftables": [{"rule": rule}]} if "chain" in args else table
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(data).encode())

    if drift:
        with pytest.raises(ValueError):
            rollback.execute(p, "c" * 64, 1240, unit_root=tmp_path, run=run)
        assert not any("delete" in c for c in calls)
    else:
        result = rollback.execute(p, "c" * 64, 1240, unit_root=tmp_path, run=run)
        assert result["host_exception_removed"]
        deleted = [c for c in calls if "delete" in c]
        assert len(deleted) == 2 and deleted[0][-2:] == ["handle", "90"]
        assert deleted[1][-3:] == ["table", "inet", "infrabadge_edge_home"]


def test_material_check_rejects_missing_loopback_san_before_install(tmp_path):
    tmp_path.chmod(0o700)
    tls = tmp_path / "tls"
    tls.mkdir(mode=0o700)
    ca, cert, key = certificates(tls, host=example()["edge_hostname"])
    for name in ("edge-ca.pem", "core-ca.pem"):
        (tls / name).write_bytes(ca.read_bytes())
        (tls / name).chmod(0o600)
    for name in ("edge.token", "probe.token"):
        (tls / name).write_text(("e" if name.startswith("edge") else "p") * 40)
        (tls / name).chmod(0o600)
    with pytest.raises(ValueError, match="loopback_and_lan_san"):
        pilot.validate_materials(tls, example(), subprocess.run)


@pytest.mark.parametrize(
    "kind", ["valid", "source_drift", "missing_file", "symlink", "wrong_sha", "writable_parent"]
)
def test_release_manifest_without_git_on_runtime(tmp_path, kind):
    tmp_path.chmod(0o700)
    value = example()
    for name in (
        "gateway/infrabadge_gateway/distributed/cli.py",
        "tools/permanent_edge/pilot.py",
        "gateway/requirements.lock",
        "deploy/m32/native/requirements-runtime.lock",
    ):
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("synthetic source")

    def git(args, **kw):
        return subprocess.CompletedProcess(
            args, 0, stdout=value["release_sha"] if "rev-parse" in args else ""
        )

    data = pilot.release_manifest(value, tmp_path, run=git)
    f = tmp_path / "source-manifest.json"
    f.write_text(json.dumps(data))
    f.chmod(0o600)
    changed = tmp_path / "tools/permanent_edge/pilot.py"
    if kind == "source_drift":
        changed.write_text("unexpected")
    elif kind == "missing_file":
        changed.unlink()
    elif kind == "symlink":
        original = tmp_path / "outside.py"
        original.write_text("synthetic source")
        changed.unlink()
        changed.symlink_to(original)
    elif kind == "writable_parent":
        changed.parent.chmod(0o777)
    elif kind == "wrong_sha":
        value = value | {"release_sha": "d" * 40}
    if kind == "valid":
        pilot.validate_release(value, tmp_path, owner=os.getuid())
    else:
        with pytest.raises(ValueError):
            pilot.validate_release(value, tmp_path, owner=os.getuid())
