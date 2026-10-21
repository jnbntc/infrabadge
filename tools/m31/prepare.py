#!/usr/bin/env python3
"""Render a candidate bundle outside Git. Never installs, starts or changes networking."""

import argparse
import dataclasses
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gateway"))
from infrabadge_gateway.lan_policy import LanPolicy, write_private


def guard_zip(output):
    package = ROOT / "gateway/infrabadge_gateway"
    entries = {
        "__main__.py": b"from infrabadge_gateway.lan_guard import main\nraise SystemExit(main())\n",
        "infrabadge_gateway/__init__.py": b"",
    }
    for name in ("lan_policy.py", "lan_guard.py"):
        entries["infrabadge_gateway/" + name] = (package / name).read_bytes()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def render(policy, output):
    output = output.expanduser().absolute()
    if (
        output.exists()
        or output.is_symlink()
        or output.is_relative_to(ROOT)
        or any(p.is_symlink() for p in output.parents)
    ):
        raise ValueError("new_output_outside_repository_required")
    output = output.resolve()
    if output.is_relative_to(ROOT.resolve()):
        raise ValueError("new_output_outside_repository_required")
    output.mkdir(parents=True, mode=0o700)
    directory = ROOT / "deploy/m31"
    for name in (
        "infrabadge-gateway.container",
        "infrabadge-lan-guard.service",
        "infrabadge-lan-guard.timer",
    ):
        text = (directory / (name + ".in")).read_text()
        text = text.replace("@IMAGE@", policy.image).replace("@ADDRESS@", policy.address)
        (output / name).write_text(text)
    write_private(output / "policy.json", dataclasses.asdict(policy))
    digest = guard_zip(output / "infrabadge-lan-guard.pyz")
    plan = dict(
        schema_version=1,
        policy_sha256=policy.fingerprint(),
        guard_zip_sha256=digest,
        changes_applied=False,
        requires_deployment_authorization=True,
        firmware_change_required=False,
        host_publications=[
            dict(address="127.0.0.1", port=8443, target=8443),
            dict(address=policy.address, port=8443, target=8444),
        ],
        proposed_firewall_rule=policy.rich_rule(),
        proposed_route_add=[
            "ip",
            "rule",
            "add",
            "priority",
            "5100",
            "from",
            policy.address + "/32",
            "to",
            policy.network,
            "ipproto",
            "tcp",
            "sport",
            "8443",
            "lookup",
            "main",
        ],
        proposed_route_delete=[
            "ip",
            "rule",
            "del",
            "priority",
            "5100",
            "from",
            policy.address + "/32",
            "to",
            policy.network,
            "ipproto",
            "tcp",
            "sport",
            "8443",
            "lookup",
            "main",
        ],
    )
    write_private(output / "deployment-plan.json", plan)
    for path in output.iterdir():
        path.chmod(0o600)
    return dict(
        status="rendered_not_installed",
        files=len(list(output.iterdir())),
        guard_zip_sha256=digest,
        host_changed=False,
        board_accessed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if os.geteuid() == 0:
            raise ValueError("normal_user_required")
        result = render(LanPolicy.load(args.policy), args.output)
    except Exception:
        raise SystemExit("Preparation stopped; no services or network changes applied.") from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
