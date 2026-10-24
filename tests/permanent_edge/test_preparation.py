"""Inert artifacts and allowlisted read-only probes; no production host access."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import ib_edge_lab as lab
import pytest
import rollback

ROOT = Path(lab.__file__).resolve().parents[2]
TEMPLATES = ROOT / "deploy/permanent_edge"


def example():
    return json.loads((TEMPLATES / "plan.synthetic.json").read_text())


@pytest.mark.parametrize(
    "field,value",
    [
        ("site", "anything"),
        ("service_user", "root"),
        ("service_user", "bad\nExecStart=/bin/false"),
        ("release_sha", "main"),
        ("lan_interface", "lan0;false"),
        ("lan_ipv4", "0.0.0.0"),
        ("lan_ipv4", 169279490),
        ("lan_ipv4", "10.23.0.255"),
        ("client_ipv4", "10.24.0.2"),
        ("lan_cidr", "0.0.0.0/0"),
        ("core_ipv4", "192.0.2.1"),
        ("edge_hostname", "bad/name"),
        ("edge_hostname", "bad..name"),
        ("edge_hostname", "bad-.name"),
        ("schema_version", True),
        ("extra", True),
    ],
)
def test_plan_rejects_broad_or_injected_values(field, value):
    p = example()
    p[field] = value
    with pytest.raises((ValueError, TypeError)):
        lab.plan(p)


def test_templates_exact_bind_nonroot_restart_and_independent_rollback(tmp_path):
    p = example()
    files = lab.render(p, TEMPLATES, phase="lan")
    assert len(files) == 6
    service = files["infrabadge-edge-home.service"]
    assert "User=ibedgehome" in service and "--bind 10.23.0.2 --port 8443" in service
    assert "Restart=on-failure" in service and "CapabilityBoundingSet=\n" in service
    assert "/etc/infrabadge-edge-home/edge.json" in service
    assert "InaccessiblePaths=-/etc/infrabadge -/var/lib/infrabadge" in service
    assert "ProtectClock=true" in service and "NoNewPrivileges=true" in service
    assert "OnActiveSec=19min" in files["infrabadge-edge-home-rollback.timer"]
    assert "--execute-authorized-rollback" in files["infrabadge-edge-home-rollback.service"]
    assert (
        'iifname "lan-test0" ip saddr 10.23.0.50/32' in files["infrabadge-edge-home.nft.proposed"]
    )
    release = tmp_path / "release"
    (release / "venv/bin").mkdir(parents=True)
    (release / "venv/bin/python").symlink_to(sys.executable)
    units = []
    for name, text in files.items():
        if name.endswith((".timer", ".service")):
            target = tmp_path / name
            target.write_text(
                text.replace("/opt/infrabadge-edges/releases/" + p["release_sha"], str(release))
            )
            units.append(str(target))
    checked = subprocess.run(
        ["systemd-analyze", "verify", "--man=no", *units], capture_output=True, timeout=15
    )
    assert checked.returncode == 0, checked.stderr.decode()


def test_preflight_reports_wrong_return_route_and_busy_port_without_changes(tmp_path):
    (tmp_path / "meminfo").write_text("MemTotal: 4000000 kB\nMemAvailable: 1000000 kB\n")
    commands = []

    def run(args):
        commands.append(args)
        if args[:3] == ["ip", "-j", "address"]:
            return '[{"addr_info":[{"local":"10.23.0.2"}]}]'
        if args[:3] == ["ip", "-j", "route"]:
            return '[{"dev":"tailscale0"}]'
        if args[0] == "ss":
            return "LISTEN 0 64 10.23.0.2:8443\n"
        if args[0] == "timedatectl":
            return "yes\n"
        return "active\n"

    result = lab.preflight(example(), run=run, proc=tmp_path)
    assert result["lan_address_present"] and not result["tcp8443_return_interface_matches"]
    assert not result["tcp8443_free"] and result["clock_synchronized"]
    assert result["firewall_dns_tls_review_required"] and not result["deployment_authorized"]
    assert not any(
        any(x in args for x in ("sudo", "start", "stop", "restart", "add", "delete"))
        for args in commands
    )
    assert "10.23.0.2" not in json.dumps(result)
    assert any("sport" in args and "8443" in args for args in commands)


def test_unavailable_preflight_tools_never_become_pass(tmp_path):
    (tmp_path / "meminfo").write_text("MemTotal: 4000000 kB\n")
    result = lab.preflight(example(), run=lambda args: None, proc=tmp_path)
    assert not result["tcp8443_free"] and not result["lan_address_present"]
    assert result["services"]["tailscaled.service"] == "unknown"


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


def rollback_plan(tmp_path):
    files = {
        "infrabadge-edge-home" + suffix: "synthetic-owned-unit\n"
        for suffix in (".service", "-probe.service", "-probe.timer")
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content)
    table = {
        "nftables": [{"table": {"family": "inet", "name": "infrabadge_edge_home", "handle": 7}}]
    }
    return {
        "schema_version": 1,
        "site": "home",
        "plan_id": "b" * 32,
        "boot_sha256": "c" * 64,
        "armed_boottime": 100.0,
        "deadline_boottime": 1240.0,
        "units_sha256": {n: hashlib.sha256(s.encode()).hexdigest() for n, s in files.items()},
        "table_sha256": rollback.table_digest(table),
        "host_accept_rule": {"handle": 90, "sha256": rollback.table_digest(host_rule())},
        "units_previously_absent": True,
    }, table


def test_rollback_exact_owned_units_and_table_only(tmp_path):
    p, table = rollback_plan(tmp_path)
    actions = []

    def run(args, **kw):
        actions.append(args)
        data = {"nftables": [{"rule": host_rule()}]} if "chain" in args else table
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(data).encode())

    result = rollback.execute(p, "c" * 64, 1240, unit_root=tmp_path, run=run)
    assert result["listener_stopped"] and result["owned_table_removed"]
    assert len(actions) == 5 and actions[0][1] == "stop"
    assert actions[-1][-4:] == ["delete", "table", "inet", "infrabadge_edge_home"]
    assert all((tmp_path / name).exists() for name in p["units_sha256"])


@pytest.mark.parametrize("kind", ["early", "host", "unit_drift", "broad", "clock", "table_drift"])
def test_rollback_rejects_drift_and_overbroad_plans(tmp_path, kind):
    p, table = rollback_plan(tmp_path)
    actions = []
    if kind == "unit_drift":
        (tmp_path / "infrabadge-edge-home.service").write_text("someone else's unit")
    elif kind == "broad":
        p["units_sha256"]["docker.service"] = "d" * 64
    elif kind == "clock":
        p["deadline_boottime"] = 1241.0
    elif kind == "table_drift":
        table["nftables"].append({"rule": {"expression": "unknown-owner"}})

    def run(args, **kw):
        actions.append(args)
        data = {"nftables": [{"rule": host_rule()}]} if "chain" in args else table
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(data).encode())

    with pytest.raises(ValueError):
        rollback.execute(
            p,
            "a" * 64 if kind == "host" else "c" * 64,
            1200 if kind == "early" else 1240,
            unit_root=tmp_path,
            run=run,
        )
    assert not any("delete" in args for args in actions)
    if kind != "table_drift":
        assert not actions


def test_rollback_ignores_only_volatile_nft_counters():
    a = {
        "nftables": [
            {"metainfo": {"version": "1"}},
            {"rule": {"handle": 1, "counter": {"packets": 3, "bytes": 50}, "accept": None}},
        ]
    }
    b = copy.deepcopy(a)
    b["nftables"][1]["rule"].update(handle=10, counter={"packets": 30, "bytes": 500})
    assert rollback.table_digest(a) == rollback.table_digest(b)
