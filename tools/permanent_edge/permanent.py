"""CASA-only persistence. No implicit installation, Core control or global nft operations.

The deployment operator must arm and verify the independent watchdog before
installing these files. This helper owns only the two reviewed C2 nft objects.
"""

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ib_edge_lab as lab
import rollback

STEM = "infrabadge-edge-home"
TABLE = "infrabadge_edge_home"
COMMENT = "infrabadge-edge-home-allow8443"
ADMIN = Path("/etc/infrabadge-edge-home-admin")
RUNTIME = Path("/run/infrabadge-edge-home-admin")
UNIT_PATHS = {
    STEM + ".service",
    STEM + "-probe.service",
    STEM + "-probe.timer",
    STEM + "-firewall.service",
    STEM + "-tls-check.service",
    STEM + "-tls-check.timer",
    STEM + ".service.d/10-permanent.conf",
}


def atomic_json(path, value):
    """Root-only caller; no secret or writable-by-Edge parent is acceptable."""
    temporary = path.with_name(path.name + ".new")
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def private_directory(path, owner=0):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("private_directory_symlink")
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_mode & 0o077:
        raise ValueError("private_directory_owner_mode")
    for parent in path.parents:
        info = parent.stat()
        if info.st_uid != owner or info.st_mode & 0o022:
            raise ValueError("private_parent_writable")


def contract(value):
    fields = {
        "schema_version",
        "plan",
        "baseline_chain_sha256",
        "expected_table_sha256",
        "expected_rule_sha256",
        "units_sha256",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise ValueError("permanent_contract_schema")
    plan = lab.plan(value["plan"])
    if (
        plan["site"] != "home"
        or plan["service_user"] != "ibedgehome"
        or plan["edge_hostname"] != plan["lan_ipv4"]
    ):
        raise ValueError("casa_exact_bind_required")
    hashes = value["units_sha256"]
    if type(hashes) is not dict or set(hashes) != UNIT_PATHS:
        raise ValueError("permanent_unit_set")
    for digest in [value[k] for k in fields if k.endswith("sha256") and k != "units_sha256"] + list(
        hashes.values()
    ):
        if type(digest) is not str or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("permanent_digest")
    return value


def verify_units(value, unit_root=Path("/etc/systemd/system"), owner=0):
    contract(value)
    for name, digest in value["units_sha256"].items():
        path = unit_root / name
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("unit_symlink")
        info = path.stat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner
            or info.st_mode & 0o022
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("permanent_unit_drift")


def nft(run, *args, batch=None):
    options = {"check": True, "capture_output": True, "text": True, "timeout": 8}
    if batch is not None:
        options["input"] = batch
    result = run(["/usr/sbin/nft", *args], **options)
    return json.loads(result.stdout) if "-j" in args else result.stdout


def objects(data):
    """Use one atomic ruleset snapshot; exclude metainfo consistently with C2."""
    own, host = [], []
    for row in data.get("nftables", []):
        for kind, item in row.items():
            if kind not in ("table", "chain", "rule") or item.get("family") != "inet":
                continue
            if (item.get("name") if kind == "table" else item.get("table")) == TABLE:
                own.append(row)
            if (
                kind in ("chain", "rule")
                and item.get("table") == "infrabadge_host"
                and (item.get("name") if kind == "chain" else item.get("chain")) == "input"
            ):
                host.append(row)
    rules = [row["rule"] for row in host if "rule" in row and row["rule"].get("comment") == COMMENT]
    return {"nftables": own}, {"nftables": host}, rules


def owned(value, data):
    table, chain, rules = objects(data)
    if (
        len(rules) != 1
        or rollback.table_digest(table) != value["expected_table_sha256"]
        or rollback.table_digest(rules[0]) != value["expected_rule_sha256"]
    ):
        raise ValueError("permanent_firewall_ownership")
    handle = rules[0].get("handle")
    if type(handle) is not int or handle <= 0:
        raise ValueError("permanent_rule_handle")
    without = {
        "nftables": [
            row for row in chain["nftables"] if row.get("rule", {}).get("handle") != handle
        ]
    }
    if rollback.table_digest(without) != value["baseline_chain_sha256"]:
        raise ValueError("host_firewall_drift")
    return handle


def remove_owned(value, data, run):
    handle = owned(value, data)
    batch = f"delete rule inet infrabadge_host input handle {handle}\ndelete table inet {TABLE}\n"
    # Both deletions are one nft transaction; never delete one then fail on the other.
    nft(run, "--check", "--file", "/dev/stdin", batch=batch)
    nft(run, "--file", "/dev/stdin", batch=batch)


def start_firewall(value, state_path, boot_hash, run=subprocess.run):
    contract(value)
    data = nft(run, "-j", "list", "ruleset")
    table, chain, rules = objects(data)
    if state_path.exists():
        state = rollback.private(state_path)
        if state != {"boot_sha256": boot_hash, "contract_sha256": rollback.table_digest(value)}:
            raise ValueError("firewall_state_drift")
        owned(value, data)
        return {"event": "edge_firewall", "already_active": True}
    if table["nftables"] or rules:
        raise ValueError("unowned_firewall_collision")
    if rollback.table_digest(chain) != value["baseline_chain_sha256"]:
        raise ValueError("host_firewall_drift")
    rows = [r["rule"] for r in chain["nftables"] if "rule" in r]
    expression = rows[-1].get("expr", []) if rows else []
    if (
        not expression
        or expression[-1] != {"drop": None}
        or any(set(item) != {"counter"} for item in expression[:-1])
        or type(rows[-1].get("handle")) is not int
        or rows[-1]["handle"] <= 0
    ):
        raise ValueError("reviewed_final_drop_required")
    plan = value["plan"]
    batch = lab.render(
        plan, lab.ROOT / "deploy/permanent_edge", "lan", host_accept_position=rows[-1]["handle"]
    )[STEM + ".nft.proposed"]
    nft(run, "--check", "--file", "/dev/stdin", batch=batch)
    # Caller must have its independent guard before this atomic transaction.
    nft(run, "--file", "/dev/stdin", batch=batch)
    try:
        owned(value, nft(run, "-j", "list", "ruleset"))
        atomic_json(
            state_path, {"boot_sha256": boot_hash, "contract_sha256": rollback.table_digest(value)}
        )
    except Exception:
        # Fail closed on persistence/publication failure, removing only exact owned objects.
        remove_owned(value, nft(run, "-j", "list", "ruleset"), run)
        raise
    return {"event": "edge_firewall", "applied": True, "objects": 2}


def stop_firewall(value, state_path, boot_hash, run=subprocess.run):
    contract(value)
    data = nft(run, "-j", "list", "ruleset")
    table, _, rules = objects(data)
    expected = {"boot_sha256": boot_hash, "contract_sha256": rollback.table_digest(value)}
    if not state_path.exists():
        if table["nftables"] or rules:
            raise ValueError("unowned_firewall_collision")
        return {"event": "edge_firewall", "already_absent": True}
    if rollback.private(state_path) != expected:
        raise ValueError("firewall_state_drift")
    if table["nftables"] or rules:
        remove_owned(value, data, run)
    state_path.unlink()
    return {"event": "edge_firewall", "removed": True}


def render(value, template_root=None):
    plan = lab.plan(value)
    if plan["site"] != "home" or plan["service_user"] != "ibedgehome":
        raise ValueError("casa_only")
    root = template_root or lab.ROOT / "deploy/permanent_edge/persistent"
    pairs = {"@RELEASE@": "/opt/infrabadge-edges/releases/" + plan["release_sha"]}
    result = {}
    for path in sorted(root.glob("*.in")):
        text = path.read_text()
        for key, replacement in pairs.items():
            text = text.replace(key, replacement)
        if re.search(r"@[A-Z_]+@", text):
            raise ValueError("unresolved_permanent_template")
        name = path.name.removesuffix(".in")
        if name == "10-permanent.conf":
            name = STEM + ".service.d/" + name
        result[name] = text
    if set(result) != UNIT_PATHS - {
        STEM + s for s in (".service", "-probe.service", "-probe.timer")
    }:
        raise ValueError("permanent_template_set")
    return result


def prepare_companions(value, expected_table, expected_rule, baseline_chain):
    """Pure preparation: operator installs only while Edge is stopped and guarded."""
    plan = lab.plan(value)
    public = lab.render(plan, lab.ROOT / "deploy/permanent_edge", "lan")
    files = {
        name: public[name]
        for name in (STEM + ".service", STEM + "-probe.service", STEM + "-probe.timer")
    }
    files.update(render(plan))
    manifest = contract(
        {
            "schema_version": 1,
            "plan": plan,
            "baseline_chain_sha256": rollback.table_digest(baseline_chain),
            "expected_table_sha256": rollback.table_digest(expected_table),
            "expected_rule_sha256": rollback.table_digest(expected_rule),
            "units_sha256": {
                name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()
            },
        }
    )
    return files, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("firewall-start", "firewall-stop", "firewall-check"))
    parser.add_argument("--execute-authorized-edge-persistence", action="store_true")
    args = parser.parse_args()
    try:
        if (
            not args.execute_authorized_edge_persistence
            or os.geteuid() != 0
            or socket.gethostname().split(".")[0] != "infrabadge-core"
        ):
            raise ValueError("explicit_root_core_approval_required")
        private_directory(ADMIN)
        value = contract(rollback.private(ADMIN / "manifest.json"))
        verify_units(value)
        private_directory(RUNTIME)
        state = RUNTIME / "firewall.json"
        boot = hashlib.sha256(Path("/proc/sys/kernel/random/boot_id").read_bytes()).hexdigest()
        if args.mode == "firewall-start":
            active = subprocess.run(
                ["/usr/bin/systemctl", "is-active", "infrabadge-firewall.service"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            if active.stdout.strip() != "active":
                raise ValueError("base_firewall_must_already_be_active")
            addresses = json.loads(
                subprocess.run(
                    [
                        "/usr/sbin/ip",
                        "-j",
                        "address",
                        "show",
                        "dev",
                        value["plan"]["lan_interface"],
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5,
                ).stdout
            )
            if not any(
                a.get("local") == value["plan"]["lan_ipv4"]
                for n in addresses
                for a in n.get("addr_info", [])
            ):
                raise ValueError("approved_lan_address_missing")
            result = start_firewall(value, state, boot)
        elif args.mode == "firewall-stop":
            result = stop_firewall(value, state, boot)
        else:
            if rollback.private(state) != {
                "boot_sha256": boot,
                "contract_sha256": rollback.table_digest(value),
            }:
                raise ValueError("firewall_state_drift")
            owned(value, nft(subprocess.run, "-j", "list", "ruleset"))
            result = {"event": "edge_firewall", "verified": True}
        print(json.dumps(result), flush=True)
        return 0
    except Exception:
        print('{"event":"edge_firewall","pass":false,"error":"manual_review_required"}', flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
