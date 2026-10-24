"""C2-only independent guard; exact ownership, no generic administration API."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

UNIT_NAMES = (
    "infrabadge-edge-home.service",
    "infrabadge-edge-home-probe.service",
    "infrabadge-edge-home-probe.timer",
)
TABLE = "infrabadge_edge_home"
COMMENT = "infrabadge-edge-home-allow8443"


def digest(data):
    def clean(v):
        if isinstance(v, dict):
            return {
                k: clean(x)
                for k, x in v.items()
                if k not in ("handle", "packets", "bytes", "metainfo")
            }
        if isinstance(v, list):
            return [clean(x) for x in v if not isinstance(x, dict) or "metainfo" not in x]
        return v

    return hashlib.sha256(
        json.dumps(clean(data), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def private(path):
    assert not any(p.is_symlink() for p in (path, *path.parents))
    info = path.stat()
    assert info.st_uid == 0 and info.st_mode & 0o077 == 0 and info.st_size < 65536
    return json.loads(path.read_bytes())


def execute(
    record, marker, boot_hash, now, run=subprocess.run, unit_root=Path("/etc/systemd/system")
):
    assert record["boot_sha256"] == boot_hash
    assert record["armed_boottime"] <= now <= record["armed_boottime"] + 180
    assert set(record["units_sha256"]) == set(UNIT_NAMES)
    if marker is not None:
        assert marker == {"plan_id": record["plan_id"], "complete": True}
        return {
            "event": "transaction_guard",
            "complete_plan_verified": True,
            "network_changed": False,
        }
    for name in UNIT_NAMES:
        file = unit_root / name
        assert (
            not file.is_symlink()
            and hashlib.sha256(file.read_bytes()).hexdigest() == record["units_sha256"][name]
        )
    run(["/usr/bin/systemctl", "stop", *UNIT_NAMES], check=True, capture_output=True, timeout=15)
    data = json.loads(
        run(
            ["/usr/sbin/nft", "-j", "list", "ruleset"], check=True, capture_output=True, timeout=3
        ).stdout
    )
    own = []
    rules = []
    for row in data.get("nftables", []):
        for kind, value in row.items():
            if kind in ("table", "chain", "rule") and value.get("family") == "inet":
                if value.get("name") == TABLE if kind == "table" else value.get("table") == TABLE:
                    own.append(row)
                if (
                    kind == "rule"
                    and value.get("table") == "infrabadge_host"
                    and value.get("chain") == "input"
                    and value.get("comment") == COMMENT
                ):
                    rules.append(value)
    if not own and not rules:
        return {"event": "transaction_guard", "listener_stopped": True, "network_changed": False}
    assert len(rules) == 1 and digest({"nftables": own}) == record["expected_table_sha256"]
    assert digest(rules[0]) == record["expected_rule_sha256"]
    handle = rules[0]["handle"]
    assert type(handle) is int and handle > 0
    batch = (
        "delete rule inet infrabadge_host input handle "
        + str(handle)
        + "\ndelete table inet "
        + TABLE
        + "\n"
    )
    run(
        ["/usr/sbin/nft", "--file", "/dev/stdin"],
        input=batch,
        text=True,
        check=True,
        capture_output=True,
        timeout=5,
    )
    return {
        "event": "transaction_guard",
        "listener_stopped": True,
        "network_changed": True,
        "exact_owned_objects_removed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--execute-authorized-transaction-guard", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0 or not args.execute_authorized_transaction_guard:
        raise ValueError("explicit_root_approval_required")
    prefix = Path("/opt/infrabadge-edges")
    if (
        not args.record.is_absolute()
        or not args.record.is_relative_to(prefix)
        or ".." in args.record.parts
    ):
        raise ValueError("edge_preparation_path_required")
    for parent in args.record.parents:
        info = parent.stat()
        if parent.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("root_owned_preparation_required")
    root = args.record.parent
    record = private(args.record)
    marker_file = root / "lan-plan-complete.private.json"
    marker = private(marker_file) if marker_file.exists() else None
    result = execute(
        record,
        marker,
        hashlib.sha256(Path("/proc/sys/kernel/random/boot_id").read_bytes()).hexdigest(),
        time.clock_gettime(time.CLOCK_BOOTTIME),
    )
    fd = os.open(
        root / "transaction-guard-result.private.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
    )
    with os.fdopen(fd, "w") as out:
        json.dump(result, out)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
