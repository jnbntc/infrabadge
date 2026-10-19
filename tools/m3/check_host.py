#!/usr/bin/env python3
"""Opt-in real host check: ephemeral localhost TLS only; no installs or board I/O.

Reports allowlisted outcomes, never raw metrics, credentials or host inventory.
"""

import argparse
import json
import os
import ssl
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gateway"), str(ROOT / "collector/fedora")]
import httpx
from infrabadge_collector.acquire import acquire
from infrabadge_collector.runtime import require_host
from infrabadge_collector.transport import submit
from infrabadge_gateway.models import Snapshot
from lab_support import container_loopback, loopback


def check(container_image=None):
    require_host()
    os_release = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text().splitlines()
        if "=" in line
    )
    if os_release.get("ID", "").strip('"') != "fedora":
        raise ValueError("fedora_host_required")
    _, baseline = acquire("workstation", "/var/home", "HOME")
    time.sleep(1)
    metrics, _ = acquire("workstation", "/var/home", "HOME", baseline)
    assert metrics["cpu"] and metrics["cpu"]["usage_percent"] is not None
    assert metrics["memory"] and metrics["disk"] and metrics["uptime_seconds"] is not None
    with tempfile.TemporaryDirectory(prefix="infrabadge-m3-host-") as temporary:
        folder = Path(temporary)
        server = (
            container_loopback(folder, container_image) if container_image else loopback(folder)
        )
        with server as (config, token, device):
            submit(config, token, metrics)
            with httpx.Client(
                verify=ssl.create_default_context(cafile=config["ca_file"]),
                trust_env=False,
                timeout=3,
            ) as client:
                headers = {"Authorization": "Bearer " + device}
                url = config["gateway_url"] + "/api/v1/devices/badge-lab/status"
                response = client.get(url, headers=headers)
                snapshot = Snapshot.model_validate(response.json())
                assert (
                    not snapshot.simulated and snapshot.expires_at == metrics["collected_at"] + 180
                )
                assert (
                    client.get(
                        url, headers={**headers, "If-None-Match": response.headers["etag"]}
                    ).status_code
                    == 304
                )
                wrong_role = client.post(
                    config["gateway_url"] + "/api/v1/collectors/workstation/metrics",
                    json=metrics,
                    headers=headers,
                )
                assert wrong_role.status_code == 401
    return dict(
        host_acquisition="passed",
        authenticated_tls_ingestion="passed",
        m2_contract="passed",
        conditional_304="passed",
        role_isolation="passed",
        cpu_temperature="available" if metrics["temperature"] else "unavailable_explicit_null",
        persistent_services_installed=False,
        board_accessed=False,
        scope="real_fedora_host_to_rootless_container_loopback"
        if container_image
        else "real_fedora_host_to_ephemeral_loopback_only",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--container-image", help="Explicit opt-in temporary rootless container, loopback only"
    )
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = check(args.container_image)
    except Exception:
        print(json.dumps({"status": "failed", "error": "host_check_failed_no_private_details"}))
        return 1
    if args.output:
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
