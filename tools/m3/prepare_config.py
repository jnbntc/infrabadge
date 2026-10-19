#!/usr/bin/env python3
"""Opt-in preparation in a NEW private folder, preserving all M2 originals.

No socket, services, board access, Wi-Fi input or device token is needed.
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gateway"), str(ROOT / "collector/fedora")]
from infrabadge_collector.runtime import load_config, private_bytes, require_host
from infrabadge_gateway.models import GatewayConfig


def prepare(output, source, ca, url, device_id):
    output = output.expanduser().absolute()
    if (
        output.exists()
        or output.is_relative_to(ROOT)
        or any(p.is_symlink() for p in output.parents)
    ):
        raise ValueError("new_private_folder_outside_repo_required")
    gateway = GatewayConfig.model_validate_json(private_bytes(source, 65536))
    if device_id not in gateway.devices or gateway.collectors:
        raise ValueError("expected_M2_source_and_logical_device")
    gateway.enable_faults = False
    for device in gateway.devices.values():
        device.fault = None
    token = secrets.token_urlsafe(32)
    payload = gateway.model_dump()
    payload["devices"][device_id]["node_id"] = "workstation"
    payload["collectors"] = {
        "workstation": {
            "display_name": "WORKSTATION",
            "token_sha256": [hashlib.sha256(token.encode()).hexdigest()],
        }
    }
    gateway = GatewayConfig.model_validate(payload)
    ca_bytes = Path(ca).read_bytes()
    if len(ca_bytes) > 16384 or b"PRIVATE KEY" in ca_bytes or b"BEGIN CERTIFICATE" not in ca_bytes:
        raise ValueError("public_ca_required")
    output.mkdir(parents=True, mode=0o700)
    (output / "ca.pem").write_bytes(ca_bytes)
    (output / "collector.token").write_text(token)
    (output / "gateway.json").write_text(gateway.model_dump_json(indent=2))
    config = dict(
        node_id="workstation",
        gateway_url=url,
        ca_file=str(output / "ca.pem"),
        mount_path="/var/home",
        mount_id="HOME",
        state_file=str(Path.home() / ".local/state/infrabadge-collector/cpu.json"),
        interval_seconds=60,
        timeout_seconds=10,
    )
    (output / "collector.json").write_text(json.dumps(config, indent=2) + "\n")
    for path in output.iterdir():
        path.chmod(0o600)
    load_config(output / "collector.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-gateway", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--device-id", default="badge-lab")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        require_host()
        prepare(args.output, args.source_gateway, args.ca_file, args.gateway_url, args.device_id)
    except Exception:
        print(
            "Preparation stopped; review private inputs locally. Original M2 files unchanged.",
            file=sys.stderr,
        )
        return 1
    print("Private M3 inputs prepared; no services or board accessed. Do not publish this folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
