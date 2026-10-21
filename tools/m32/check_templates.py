#!/usr/bin/env python3
"""Validate inert M3.2 inputs; optional isolated Quadlet dry-run, never installs."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gateway"))
from infrabadge_gateway.distributed.config import CoreConfig


def check(quadlet=False):
    config = CoreConfig.model_validate_json((ROOT / "deploy/m32/core.example.json").read_text())
    assert not config.nodes and not config.collectors and not config.devices
    assert all(not s.enabled for s in config.sites.values())
    grants = json.loads((ROOT / "deploy/m32/grants.proposal.json").read_text())
    assert grants["not_a_tailnet_policy"] and grants["requires_organizational_approval"]
    assert all(
        g["ip"] == ["tcp:9443"] and "*" not in json.dumps(g) for g in grants["proposed_grants"]
    )
    with tempfile.TemporaryDirectory() as folder:
        for mode in ("core", "edge"):
            text = (ROOT / f"deploy/m32/infrabadge-m32-{mode}.container.in").read_text()
            assert "PublishPort=0.0.0.0" not in text and "Network=host" not in text
            text = (
                text.replace("@IMAGE_ID@", "sha256:" + "a" * 64)
                .replace("@TAILNET_IPV4@", "192.0.2.1")
                .replace("@LAN_IPV4@", "192.0.2.2")
            )
            (Path(folder) / f"infrabadge-m32-{mode}.container").write_text(text)
        if quadlet:
            result = subprocess.run(
                [
                    "/usr/lib/systemd/system-generators/podman-system-generator",
                    "--user",
                    "--dryrun",
                ],
                env=os.environ | {"QUADLET_UNIT_DIRS": folder},
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
            assert all(
                f"infrabadge-m32-{mode}.service" in result.stdout for mode in ("core", "edge")
            )
    return dict(
        status="PASS", inputs="empty_or_synthetic", quadlet_dryrun=quadlet, host_changed=False
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quadlet", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.quadlet)))
