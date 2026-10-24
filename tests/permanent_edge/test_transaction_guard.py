import hashlib
import json
import subprocess

import pytest
import transaction_guard as guard


@pytest.mark.parametrize(
    "kind", ["absent", "present", "drift", "duplicate", "committed", "unit_drift"]
)
def test_guard_exact_ownership_and_no_generic_changes(tmp_path, kind):
    units = {}
    for name in guard.UNIT_NAMES:
        (tmp_path / name).write_text("synthetic own unit")
        units[name] = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
    table = [
        {"table": {"family": "inet", "name": guard.TABLE, "handle": 1}},
        {"chain": {"family": "inet", "table": guard.TABLE, "name": "lan_input", "handle": 2}},
    ]
    rule = {
        "family": "inet",
        "table": "infrabadge_host",
        "chain": "input",
        "handle": 77,
        "comment": guard.COMMENT,
        "expr": [{"accept": None}],
    }
    rec = {
        "boot_sha256": "b" * 64,
        "armed_boottime": 100,
        "units_sha256": units,
        "plan_id": "p",
        "expected_table_sha256": guard.digest({"nftables": table}),
        "expected_rule_sha256": guard.digest(rule),
    }
    data = {"nftables": table + [{"rule": rule}]} if kind != "absent" else {"nftables": []}
    if kind == "drift":
        rule["expr"] = [{"drop": None}]
    if kind == "duplicate":
        data["nftables"].append({"rule": rule})
    if kind == "unit_drift":
        (tmp_path / guard.UNIT_NAMES[0]).write_text("somebody else")
    calls = []

    def run(args, **kw):
        calls.append((args, kw))
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(data))

    marker = {"plan_id": "p", "complete": True} if kind == "committed" else None
    if kind in ("drift", "duplicate", "unit_drift"):
        with pytest.raises(AssertionError):
            guard.execute(rec, marker, "b" * 64, 160, run, tmp_path)
        assert not any("--file" in c[0] for c in calls)
    else:
        result = guard.execute(rec, marker, "b" * 64, 160, run, tmp_path)
        assert result["network_changed"] == (kind == "present")
        if kind == "present":
            assert (
                calls[-1][1]["input"]
                == "delete rule inet infrabadge_host input handle 77\ndelete table inet infrabadge_edge_home\n"
            )
        if kind == "committed":
            assert not calls


@pytest.mark.parametrize(
    "boot,now,marker",
    [
        ("wrong", 160, None),
        ("b" * 64, 281, None),
        ("b" * 64, 160, {"plan_id": "wrong", "complete": True}),
    ],
)
def test_guard_rejects_wrong_boot_expired_window_or_wrong_commit(tmp_path, boot, now, marker):
    calls = []
    rec = {
        "boot_sha256": "b" * 64,
        "armed_boottime": 100,
        "units_sha256": dict.fromkeys(guard.UNIT_NAMES, "not-read"),
        "plan_id": "p",
    }
    with pytest.raises(AssertionError):
        guard.execute(rec, marker, boot, now, lambda *a, **k: calls.append(a), tmp_path)
    assert not calls


@pytest.mark.parametrize("uid,flag", [(1000, True), (0, False)])
def test_cli_requires_root_and_explicit_approval(monkeypatch, uid, flag):
    monkeypatch.setattr(guard.os, "geteuid", lambda: uid)
    arguments = ["guard", "--record", "/opt/infrabadge-edges/private/guard.json"]
    if flag:
        arguments.append("--execute-authorized-transaction-guard")
    monkeypatch.setattr("sys.argv", arguments)
    with pytest.raises(ValueError, match="explicit_root_approval_required"):
        guard.main()


@pytest.mark.parametrize(
    "path", ["/tmp/not-an-edge-plan.json", "/opt/infrabadge-edges/../outside.json"]
)
def test_cli_refuses_records_outside_edge_preparation(monkeypatch, path):
    monkeypatch.setattr(guard.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "guard",
            "--record",
            path,
            "--execute-authorized-transaction-guard",
        ],
    )
    with pytest.raises(ValueError, match="edge_preparation_path_required"):
        guard.main()
