"""Unprivileged host oneshot. READ commands only; never configures the network."""

import argparse
import hashlib
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

from .lan_policy import LanPolicy, boottime, lease_valid, write_private


def read(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=2).rstrip(
        "\n"
    )


def inspect_network(policy, reader=read, resolver=socket.getaddrinfo):
    """No credentials, inventory, packets or mutation command is requested."""
    addresses = json.loads(reader("ip", "-j", "address", "show", "dev", policy.interface))
    network = ipaddress.ip_network(policy.network)
    if not any(
        "UP" in d.get("flags", [])
        and any(
            a.get("local") == policy.address and a.get("prefixlen") == network.prefixlen
            for a in d.get("addr_info", [])
        )
        for d in addresses
    ):
        raise ValueError("interface_not_authorized")
    active = reader(
        "nmcli", "--escape", "no", "-g", "GENERAL.CON-UUID", "device", "show", policy.interface
    )
    if active != policy.connection_uuid:
        raise ValueError("connection_not_authorized")
    ssid = reader(
        "nmcli",
        "--escape",
        "no",
        "-g",
        "802-11-wireless.ssid",
        "connection",
        "show",
        "uuid",
        active,
    )
    if hashlib.sha256(ssid.encode()).hexdigest() != policy.ssid_sha256:
        raise ValueError("ssid_not_authorized")
    zone = reader("firewall-cmd", "--get-zone-of-interface=" + policy.interface)
    if zone != policy.firewall_zone:
        raise ValueError("firewall_zone_changed")
    rules = reader("firewall-cmd", "--zone=" + zone, "--list-all")
    if hashlib.sha256(rules.encode()).hexdigest() != policy.firewall_sha256:
        raise ValueError("firewall_review_required")
    ports = reader("firewall-cmd", "--zone=" + zone, "--list-ports").split()
    for entry in ports:
        port, protocol = entry.split("/")
        start, _, end = port.partition("-")
        if protocol == "tcp" and int(start) <= 8443 <= int(end or start):
            raise ValueError("broad_tcp8443_allowance")
    # An exact source/destination rule must already have been reviewed/applied.
    reader("firewall-cmd", "--zone=" + zone, "--query-rich-rule=" + policy.rich_rule())
    peer = next(str(p) for p in network.hosts() if str(p) != policy.address)
    route = json.loads(
        reader(
            "ip",
            "-j",
            "route",
            "get",
            peer,
            "from",
            policy.address,
            "ipproto",
            "tcp",
            "sport",
            "8443",
            "dport",
            "50000",
        )
    )
    if not route or route[0].get("dev") != policy.interface:
        raise ValueError("return_route_not_authorized")
    if policy.hostname.endswith(".local"):
        resolved = json.loads(
            reader(
                "busctl",
                "--json=short",
                "call",
                "org.freedesktop.Avahi",
                "/",
                "org.freedesktop.Avahi.Server",
                "ResolveHostName",
                "iisiu",
                str(socket.if_nametoindex(policy.interface)),
                "0",
                policy.hostname,
                "0",
                "0",
            )
        )
        if policy.address not in resolved["data"]:
            raise ValueError("interface_dns_mismatch")
    elif {
        r[4][0]
        for r in resolver(policy.hostname, 8443, family=socket.AF_INET, type=socket.SOCK_STREAM)
    } != {policy.address}:
        raise ValueError("dns_mismatch")


def refresh(policy, lease, reader=read, clock=boottime, resolver=socket.getaddrinfo):
    observed = clock()
    allowed = False
    try:
        inspect_network(policy, reader, resolver)
        allowed = 0 <= clock() - observed < 7
    except (OSError, ValueError, TypeError, KeyError, StopIteration, subprocess.SubprocessError):
        pass
    write_private(
        lease,
        dict(
            schema_version=1,
            policy_sha256=policy.fingerprint(),
            observed_boot_seconds=observed,
            allowed=allowed,
        ),
    )
    return allowed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--require-approved", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() == 0 or Path("/run/.containerenv").exists() or Path("/.dockerenv").exists():
        return 1
    try:
        policy = LanPolicy.load(args.policy)
        if args.check_only:
            return 0 if lease_valid(args.lease, policy) else 1

        def expired(_signal, _frame):
            raise TimeoutError("guard_deadline")

        signal.signal(signal.SIGALRM, expired)
        signal.alarm(7)
        try:
            allowed = refresh(policy, args.lease)
        finally:
            signal.alarm(0)
        print(
            json.dumps(dict(component="lan_guard", event="approved" if allowed else "unavailable"))
        )
        return 0 if allowed or not args.require_approved else 1
    except Exception:
        print('{"component":"lan_guard","event":"unavailable"}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
