#!/usr/bin/env python3
"""Prepare NEW private lab inputs. Never opens USB or changes network/services."""

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "gateway"), str(ROOT / "collector/fedora"), str(ROOT / "tools/m2")]
from infrabadge_collector.runtime import private_bytes, require_host
from infrabadge_gateway.models import GatewayConfig
from provision import read_private, wire


def read(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=15).strip()


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def prepare(output, deployment, device_path, *, loopback_only=False):
    require_host()
    output = output.expanduser().absolute()
    if (
        output.exists()
        or output.is_relative_to(ROOT)
        or any(p.is_symlink() for p in output.parents)
    ):
        raise ValueError("new_private_folder_outside_git_required")
    meta = json.loads(private_bytes(deployment / "deployment.json", 8192))
    ca, cert, key = (deployment / "tls" / name for name in ("ca.pem", "server.pem", "server.key"))
    private_bytes(key, 16384)
    gateway_path = Path(meta["gateway_config"])
    gateway = GatewayConfig.model_validate_json(private_bytes(gateway_path, 65536))
    device = read_private(device_path)
    identity = gateway.devices[device["device_id"]]
    if (
        identity.node_id is None
        or hashlib.sha256(device["token"].encode()).hexdigest() not in identity.token_sha256
    ):
        raise ValueError("device_gateway_binding")
    hostname = urlsplit(device["gateway_url"]).hostname
    if device["ca_pem"] != ca.read_text():
        raise ValueError("existing_m3_trust_required")
    certificate = ssl._ssl._test_decode_cert(str(cert))
    now = dt.datetime.now(dt.timezone.utc)
    if (
        ("DNS", hostname) not in certificate["subjectAltName"]
        or not ssl.cert_time_to_seconds(certificate["notBefore"])
        <= now.timestamp()
        < ssl.cert_time_to_seconds(certificate["notAfter"]) - 1200
        or read("timedatectl", "show", "-p", "NTPSynchronized", "--value") != "yes"
    ):
        raise ValueError("hostname_certificate_or_time")
    interface = network = route_needed = None
    address = {"local": "127.0.0.1"}
    if not loopback_only:
        interface = next(
            row.split(":")[0]
            for row in read("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device").splitlines()
            if ":wifi:connected" in row
        )
        uuid = read(
            "nmcli", "--escape", "no", "-g", "GENERAL.CON-UUID", "device", "show", interface
        )
        if (
            read(
                "nmcli",
                "--escape",
                "no",
                "-g",
                "802-11-wireless.ssid",
                "connection",
                "show",
                "uuid",
                uuid,
            )
            != device["ssid"]
        ):
            raise ValueError("active_wifi_mismatch")
        address = next(
            a
            for d in json.loads(read("ip", "-j", "address", "show", "dev", interface))
            for a in d["addr_info"]
            if a["family"] == "inet" and a["scope"] == "global"
        )
        network = ipaddress.ip_network(
            address["local"] + "/" + str(address["prefixlen"]), strict=False
        )
        resolved = json.loads(
            read(
                "busctl",
                "--json=short",
                "call",
                "org.freedesktop.Avahi",
                "/",
                "org.freedesktop.Avahi.Server",
                "ResolveHostName",
                "iisiu",
                str(socket.if_nametoindex(interface)),
                "0",
                hostname,
                "0",
                "0",
            )
        )
        if address["local"] not in resolved["data"]:
            raise ValueError("wifi_mdns_mismatch")
        peer = str(next(a for a in network.hosts() if str(a) != address["local"]))
        route = json.loads(
            read(
                "ip",
                "-j",
                "route",
                "get",
                peer,
                "from",
                address["local"],
                "ipproto",
                "tcp",
                "sport",
                "8443",
                "dport",
                "50000",
            )
        )[0]
        if route.get("dev") not in (interface, "tailscale0"):
            raise ValueError("unreviewed_return_route")
        route_needed = route.get("dev") != interface
        if route_needed and any(
            v.get("priority") == 5100 for v in json.loads(read("ip", "-j", "rule", "show"))
        ):
            raise ValueError("route_priority_occupied")
    wire(device, int(now.timestamp()))
    output.mkdir(parents=True, mode=0o700)
    observer = dict(
        listen_address=address["local"],
        device_id=device["device_id"],
        gateway_config=str(gateway_path),
        ca_file=str(ca),
        server_cert=str(cert),
        server_key=str(key),
    )
    write_private(output / "observer.json", observer)
    write_private(
        output / "client.json", dict(device_id=device["device_id"], token=device["token"])
    )
    if not loopback_only:
        write_private(output / "device.json", device)
    plan = dict(
        schema_version=1,
        prepared_utc=now.isoformat(),
        interface=interface,
        address=address["local"],
        network=str(network) if network is not None else None,
        hostname=hostname,
        route_required=route_needed,
        route_priority=5100,
        tcp_source_port=8443,
        maximum_seconds=1200,
        board_flash_permitted=False,
        provision_count=0 if loopback_only else 1,
        authorization="loopback_check_only"
        if loopback_only
        else "required_new_m3_observation_session",
        original_host_services_unchanged=True,
        electrical_measurements="DEFERRED",
    )
    write_private(output / "plan.json", plan)
    return dict(
        status="prepared_not_executed",
        private=str(output),
        route_exception_needed=route_needed,
        flash_required=False,
        board_accessed=False,
        host_configuration_changed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--deployment", required=True, type=Path)
    parser.add_argument("--device-config", required=True, type=Path)
    parser.add_argument("--loopback-only", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            prepare(
                args.output, args.deployment, args.device_config, loopback_only=args.loopback_only
            )
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Preparation stopped; inspect private inputs. No board or network changes."
        ) from None
