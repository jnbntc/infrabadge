#!/usr/bin/env python3
"""Validate synthetic deployment artifacts without installing or starting anything."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from prepare import ROOT, LanPolicy, render


def check(quadlet=False):
    example = ROOT / "deploy/m31/policy.example.json"
    policy = LanPolicy(**json.loads(example.read_text()))
    with tempfile.TemporaryDirectory(prefix="infrabadge-m31-") as temporary:
        output = Path(temporary) / "candidate"
        render(policy, output)
        subprocess.run(
            [sys.executable, "-I", str(output / "infrabadge-lan-guard.pyz"), "--help"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            [
                "systemd-analyze",
                "--user",
                "verify",
                str(output / "infrabadge-lan-guard.service"),
                str(output / "infrabadge-lan-guard.timer"),
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        if quadlet:
            generated = subprocess.run(
                [
                    "/usr/lib/systemd/system-generators/podman-system-generator",
                    "--user",
                    "--dryrun",
                ],
                env=os.environ | {"QUADLET_UNIT_DIRS": str(output)},
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
            if (
                "infrabadge-gateway.service" not in generated.stdout
                or "127.0.0.1:8443:8443" not in generated.stdout
                or policy.address + ":8443:8444" not in generated.stdout
                or "0.0.0.0:8443" in generated.stdout
                or "--network=host" in generated.stdout
            ):
                raise ValueError("unexpected_generated_unit")
    return dict(
        status="PASS",
        inputs="synthetic",
        guard_zip=True,
        unit_syntax=True,
        quadlet_dryrun=quadlet,
        services_started=False,
        host_network_changed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quadlet", action="store_true", help="Also dry-run existing Podman generator"
    )
    args = parser.parse_args()
    print(json.dumps(check(args.quadlet)))


if __name__ == "__main__":
    main()
