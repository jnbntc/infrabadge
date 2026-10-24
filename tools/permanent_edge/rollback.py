"""Independent, ownership-checked rollback for a FUTURE authorized edge trial.

Only stops new units and retires its exact unchanged nft table. Never restores
SQLite/config or deletes backups. Templates must remain disabled during trial.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path


def private(path, owner=0):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner
            or info.st_mode & 0o077
            or info.st_size > 65536
        ):
            raise ValueError("private_plan")
        return json.loads(os.read(fd, 65537))
    finally:
        os.close(fd)


def table_digest(data):
    def clean(value):
        if isinstance(value, dict):
            return {
                k: clean(v)
                for k, v in value.items()
                if k not in ("handle", "packets", "bytes", "metainfo")
            }
        if isinstance(value, list):
            return [clean(v) for v in value if not isinstance(v, dict) or "metainfo" not in v]
        return value

    return hashlib.sha256(
        json.dumps(clean(data), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def check(value, boot_hash, boottime):
    fields = {
        "schema_version",
        "site",
        "plan_id",
        "boot_sha256",
        "armed_boottime",
        "deadline_boottime",
        "units_sha256",
        "table_sha256",
        "units_previously_absent",
    }
    if (
        type(value) is not dict
        or set(value) not in (fields, fields | {"host_accept_rule"})
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["site"] not in ("home", "work")
        or value["units_previously_absent"] is not True
    ):
        raise ValueError("rollback_schema")
    for key, size in (("plan_id", 32), ("boot_sha256", 64), ("table_sha256", 64)):
        if key == "table_sha256" and value[key] is None:
            continue
        if type(value[key]) is not str or not re.fullmatch(
            "[a-f0-9]{" + str(size) + "}", value[key]
        ):
            raise ValueError("rollback_id")
    owned = value.get("host_accept_rule")
    if owned is not None and (
        value["site"] != "home"
        or value["table_sha256"] is None
        or type(owned) is not dict
        or set(owned) != {"handle", "sha256"}
        or type(owned["handle"]) is not int
        or owned["handle"] <= 0
        or type(owned["sha256"]) is not str
        or not re.fullmatch("[a-f0-9]{64}", owned["sha256"])
    ):
        raise ValueError("host_exception_ownership")
    a, b = value["armed_boottime"], value["deadline_boottime"]
    if (
        any(type(n) not in (int, float) for n in (a, b))
        or not 0 <= a <= boottime
        or not 60 <= b - a <= 1140
        or value["boot_sha256"] != boot_hash
    ):
        raise ValueError("rollback_clock_or_host")
    stem = "infrabadge-edge-" + value["site"]
    units = {stem + suffix for suffix in (".service", "-probe.service", "-probe.timer")}
    if (
        type(value["units_sha256"]) is not dict
        or set(value["units_sha256"]) != units
        or any(
            type(v) is not str or not re.fullmatch("[a-f0-9]{64}", v)
            for v in value["units_sha256"].values()
        )
    ):
        raise ValueError("rollback_ownership")
    return units


def execute(value, boot_hash, boottime, unit_root=Path("/etc/systemd/system"), run=subprocess.run):
    units = check(value, boot_hash, boottime)
    if boottime < value["deadline_boottime"]:
        raise ValueError("rollback_not_due")
    # Hash all owned files before ANY state change. Never stop somebody else's unit.
    for name in units:
        p = unit_root / name
        if (
            p.is_symlink()
            or not p.is_file()
            or hashlib.sha256(p.read_bytes()).hexdigest() != value["units_sha256"][name]
        ):
            raise ValueError("unit_drift")
    stem = "infrabadge-edge-" + value["site"]
    run(
        [
            "/usr/bin/systemctl",
            "stop",
            stem + "-probe.timer",
            stem + "-probe.service",
            stem + ".service",
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    if value["table_sha256"] is None:
        return {
            "event": "edge_rollback",
            "listener_stopped": True,
            "owned_table_removed": False,
            "firewall_changed": False,
            "unit_files_preserved": True,
        }
    nft = "/usr/sbin/nft" if Path("/usr/sbin/nft").is_file() else "/usr/bin/nft"
    table = "infrabadge_edge_" + value["site"]
    before = run(
        [nft, "-j", "list", "table", "inet", table], check=True, capture_output=True, timeout=3
    )
    if table_digest(json.loads(before.stdout)) != value["table_sha256"]:
        raise ValueError("table_drift_listener_already_stopped")
    owned = value.get("host_accept_rule")
    if owned is not None:
        chain = run(
            [nft, "-j", "list", "chain", "inet", "infrabadge_host", "input"],
            check=True,
            capture_output=True,
            timeout=3,
        )
        rules = [
            x["rule"]
            for x in json.loads(chain.stdout).get("nftables", [])
            if "rule" in x and x["rule"].get("handle") == owned["handle"]
        ]
        if (
            len(rules) != 1
            or rules[0].get("comment") != "infrabadge-edge-home-allow8443"
            or table_digest(rules[0]) != owned["sha256"]
            or not any(
                x.get("match", {}).get("left") == {"payload": {"protocol": "tcp", "field": "dport"}}
                and x["match"].get("right") == 8443
                for x in rules[0].get("expr", [])
            )
            or {"accept": None} not in rules[0].get("expr", [])
        ):
            raise ValueError("host_exception_drift_listener_already_stopped")
        run(
            [
                nft,
                "delete",
                "rule",
                "inet",
                "infrabadge_host",
                "input",
                "handle",
                str(owned["handle"]),
            ],
            check=True,
            capture_output=True,
            timeout=3,
        )
    run([nft, "delete", "table", "inet", table], check=True, capture_output=True, timeout=3)
    return {
        "event": "edge_rollback",
        "listener_stopped": True,
        "owned_table_removed": True,
        "unit_files_preserved": True,
        "host_exception_removed": owned is not None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--execute-authorized-rollback", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        if os.geteuid() != 0 or args.check_only == args.execute_authorized_rollback:
            raise ValueError("explicit_root_approval_required")
        value = private(args.plan)
        if args.plan != Path("/run/infrabadge-edge-" + value["site"] + "/rollback.json"):
            raise ValueError("plan_location")
        boot_hash = hashlib.sha256(Path("/proc/sys/kernel/random/boot_id").read_bytes()).hexdigest()
        now = time.clock_gettime(time.CLOCK_BOOTTIME)
        check(value, boot_hash, now)
        commit = args.plan.parent / "committed.json"
        if commit.exists():
            if private(commit) != {"plan_id": value["plan_id"], "committed": True}:
                raise ValueError("commit_marker")
            result = {"event": "edge_rollback", "deployment_committed": True, "changed": False}
        elif args.check_only:
            result = {"event": "edge_rollback", "plan_valid": True, "changed": False}
        else:
            result = execute(value, boot_hash, now)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print('{"event":"edge_rollback","pass":false,"error":"manual_review_required"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
