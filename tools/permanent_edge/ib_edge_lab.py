"""Inert edge preparation and explicit read-only checks. Never installs services."""

import argparse
import contextlib
import hashlib
import http.client
import ipaddress
import json
import os
import platform
import re
import signal
import ssl
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gateway"))


def plan(value):
    fields = {
        "schema_version",
        "site",
        "service_user",
        "release_sha",
        "lan_interface",
        "lan_ipv4",
        "lan_cidr",
        "client_ipv4",
        "core_ipv4",
        "edge_hostname",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise ValueError("plan_schema")
    if value["site"] not in ("home", "work"):
        raise ValueError("site")
    for name, expression in (
        ("service_user", r"[a-z_][a-z0-9_-]{0,30}"),
        ("release_sha", r"[a-f0-9]{40}"),
        ("lan_interface", r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,14}"),
        ("edge_hostname", r"[a-z0-9][a-z0-9.-]{1,126}[a-z0-9]"),
    ):
        if type(value[name]) is not str or not re.fullmatch(expression, value[name]):
            raise ValueError("plan_field")
    if any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in value["edge_hostname"].split(".")
    ):
        raise ValueError("dns_labels")
    if value["service_user"] in ("root", "nobody"):
        raise ValueError("dedicated_unprivileged_user")
    if any(type(value[k]) is not str for k in ("lan_cidr", "lan_ipv4", "client_ipv4", "core_ipv4")):
        raise ValueError("address_string_required")
    network = ipaddress.IPv4Network(value["lan_cidr"], strict=True)
    lan, client, core = (
        ipaddress.IPv4Address(value[k]) for k in ("lan_ipv4", "client_ipv4", "core_ipv4")
    )
    rfc1918 = [ipaddress.IPv4Network(x) for x in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    if (
        not any(network.subnet_of(n) for n in rfc1918)
        or network.prefixlen > 30
        or any(
            a not in network or a in (network.network_address, network.broadcast_address)
            for a in (lan, client)
        )
        or lan == client
        or core not in ipaddress.IPv4Network("100.64.0.0/10")
    ):
        raise ValueError("explicit_lan_tailnet_required")
    return dict(value)


def private_json(path):
    # Reuse the gateway's owned-private-file and duplicate-key policy.
    from infrabadge_gateway.distributed.private import read_json

    return read_json(path)


def render(value, template_root):
    value = plan(value)
    pairs = {
        "@SITE@": value["site"],
        "@EDGE_USER@": value["service_user"],
        "@RELEASE@": "/opt/infrabadge-edges/releases/" + value["release_sha"],
        "@LAN_IPV4@": value["lan_ipv4"],
        "@LAN_INTERFACE@": value["lan_interface"],
        "@LAN_CIDR@": value["lan_cidr"],
    }
    result = {}
    for source in sorted(Path(template_root).glob("*.in")):
        text = source.read_text()
        for key, replacement in pairs.items():
            text = text.replace(key, replacement)
        if re.search(r"@[A-Z_]+@", text):
            raise ValueError("unresolved_template")
        result[source.name.removesuffix(".in").replace("SITE", value["site"])] = text
    if len(result) != 6:
        raise ValueError("template_set")
    return result


def command(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=3, check=True)
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def preflight(value, run=command, proc=Path("/proc")):
    """Allowlisted metadata, no packets, no sudo, no raw addresses in output."""
    value = plan(value)
    memory = {}
    for row in (proc / "meminfo").read_text().splitlines():
        parts = row.split()
        if len(parts) >= 2 and parts[0] in ("MemTotal:", "MemAvailable:"):
            memory[parts[0][:-1]] = int(parts[1]) * 1024
    available = memory.get("MemAvailable", 0)
    addresses = run(["ip", "-j", "address", "show", "dev", value["lan_interface"]])
    route = run(
        [
            "ip",
            "-j",
            "route",
            "get",
            value["client_ipv4"],
            "from",
            value["lan_ipv4"],
            "ipproto",
            "tcp",
            "sport",
            "8443",
            "dport",
            "49152",
        ]
    )
    core_route = run(["ip", "-j", "route", "get", value["core_ipv4"]])
    listeners = run(["ss", "-H", "-lnt", "sport = :8443"])
    synchronized = run(["timedatectl", "show", "--property=NTPSynchronized", "--value"])
    services = {}
    for unit in (
        "docker.service",
        "containerd.service",
        "tailscaled.service",
        "infrabadge-m32-collector.timer",
        "infrabadge-m32-nas01-collector.timer",
    ):
        text = run(["systemctl", "show", "--property=ActiveState", "--value", unit])
        services[unit] = (
            text.strip()
            if text
            and text.strip()
            in ("active", "inactive", "failed", "activating", "deactivating", "reloading")
            else "unknown"
        )

    def decoded(text):
        try:
            v = json.loads(text) if text is not None else None
            return v if isinstance(v, list) else None
        except (ValueError, TypeError):
            return None

    addr, selected, core_selected = decoded(addresses), decoded(route), decoded(core_route)
    bound = addr is not None and any(
        a.get("local") == value["lan_ipv4"]
        for interface in addr
        if isinstance(interface, dict)
        for a in interface.get("addr_info", [])
    )
    prefix_matches = addr is not None and any(
        a.get("local") == value["lan_ipv4"]
        and a.get("prefixlen") == ipaddress.IPv4Network(value["lan_cidr"]).prefixlen
        for interface in addr
        if isinstance(interface, dict)
        for a in interface.get("addr_info", [])
    )
    core_via_tailnet = (
        core_selected is not None
        and bool(core_selected)
        and all(isinstance(r, dict) and r.get("dev") == "tailscale0" for r in core_selected)
    )
    correct_route = (
        selected is not None
        and bool(selected)
        and all(isinstance(r, dict) and r.get("dev") == value["lan_interface"] for r in selected)
    )
    return {
        "event": "edge_preflight",
        "read_only": True,
        "machine": platform.machine(),
        "python": platform.python_version(),
        "memory_available_bytes": available,
        "memory_total_bytes": memory.get("MemTotal"),
        "lan_address_present": bound,
        "lan_prefix_matches": prefix_matches,
        "core_route_uses_tailscale": core_via_tailnet,
        "tcp8443_return_interface_matches": correct_route,
        "tcp8443_free": listeners is not None and not listeners.strip(),
        "clock_synchronized": synchronized is not None and synchronized.strip() == "yes",
        "services": services,
        "firewall_dns_tls_review_required": True,
        "deployment_authorized": False,
    }


@contextlib.contextmanager
def deadline(seconds):
    if signal.getitimer(signal.ITIMER_REAL)[0]:
        raise ValueError("existing_alarm")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_number, _frame):
        raise TimeoutError("probe_deadline")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def probe(value, clock=time.time, connection_factory=http.client.HTTPSConnection):
    """Dedicated probe device identity; never reuse the physical badge's token."""
    from urllib.parse import urlsplit

    from infrabadge_gateway.app import bounded_json
    from infrabadge_gateway.distributed.presentation import Presentation
    from infrabadge_gateway.distributed.private import private_bytes

    if type(value) is not dict or set(value) != {
        "url",
        "ca_file",
        "token_file",
        "probe_device_id",
        "minimum_leaf_seconds",
    }:
        raise ValueError("probe_schema")
    url = urlsplit(value["url"])
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
        or url.port != 8443
    ):
        raise ValueError("probe_origin")
    if not re.fullmatch(r"probe-[a-z0-9_-]{1,26}", value["probe_device_id"]):
        raise ValueError("dedicated_probe_identity")
    minimum = value["minimum_leaf_seconds"]
    if type(minimum) is not int or not 0 <= minimum <= 30 * 86400:
        raise ValueError("renewal_horizon")
    token = private_bytes(value["token_file"], 128).decode("ascii").strip()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{32,96}", token):
        raise ValueError("probe_credential")
    context = ssl.create_default_context(cafile=value["ca_file"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    path = "/api/v2/devices/" + value["probe_device_id"] + "/status"
    tag = None
    expires = None
    got_304 = False
    with deadline(6):
        for attempt in range(2):
            connection = connection_factory(url.hostname, url.port, context=context, timeout=4)
            try:
                connection.connect()
                if (
                    minimum
                    and ssl.cert_time_to_seconds(connection.sock.getpeercert()["notAfter"])
                    - clock()
                    < minimum
                ):
                    raise ValueError("leaf_renewal_required")
                h = {"Authorization": "Bearer " + token}
                if tag:
                    h["If-None-Match"] = tag
                connection.request("GET", path, headers=h)
                response = connection.getresponse()
                headers = response.getheaders()
                if sum(len(k) + len(v) for k, v in headers) > 8192:
                    raise ValueError("header_limit")
                for name in ("etag", "x-infrabadge-expires", "x-infrabadge-now"):
                    if sum(k.lower() == name for k, _ in headers) != 1:
                        raise ValueError("header_cardinality")
                content = response.read(4097)
                server_now = int(response.getheader("x-infrabadge-now", "0"))
                remote_expiry = int(response.getheader("x-infrabadge-expires", "0"))
                received = response.getheader("etag", "")
                if (
                    response.status not in ((200,) if attempt == 0 else (200, 304))
                    or len(content) > 4096
                    or abs(server_now - int(clock())) > 60
                    or not int(clock()) < remote_expiry <= server_now + 3600
                    or not re.fullmatch('"[a-f0-9]{64}"', received)
                ):
                    raise ValueError("probe_response")
                if response.status == 200:
                    model = Presentation.model_validate(bounded_json(content))
                    if (
                        model.device_id != value["probe_device_id"]
                        or model.expires_at != remote_expiry
                        or not model.generated_at <= int(clock()) < model.expires_at
                        or received != '"' + hashlib.sha256(content).hexdigest() + '"'
                    ):
                        raise ValueError("probe_contract")
                    if attempt and received == tag:
                        raise ValueError("conditional_200_unchanged")
                    tag, expires = received, remote_expiry
                else:
                    if content or received != tag or remote_expiry != expires:
                        raise ValueError("probe_304_lifetime")
                    got_304 = True
            finally:
                connection.close()
    return {
        "event": "edge_probe",
        "pass": True,
        "tls_verified": True,
        "etag_304": got_304,
        "snapshot_changed": not got_304,
        "deadline_seconds": 6,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("render", "preflight", "probe"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inspect-local-authorized", action="store_true")
    parser.add_argument("--authorized-administrative-read", action="store_true")
    args = parser.parse_args()
    try:
        value = private_json(args.config)
        if args.mode == "render":
            from infrabadge_gateway.distributed.private import private_parent

            target = private_parent(args.output)
            files = render(value, ROOT / "deploy/permanent_edge")
            # One new directory, never an existing unit/config path.
            target.mkdir(mode=0o700)
            for name, text in files.items():
                fd = os.open(target / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(text)
            result = {"event": "edge_templates", "files": len(files), "installed": False}
        elif args.mode == "preflight":
            if (
                not args.inspect_local_authorized
                or os.geteuid() == 0
                and not args.authorized_administrative_read
            ):
                raise ValueError("read_authorization_required")
            result = preflight(value)
        else:
            if os.geteuid() == 0:
                raise ValueError("unprivileged_probe_required")
            result = probe(value)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print('{"event":"edge_preparation","pass":false,"error":"check_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
