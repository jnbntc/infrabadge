"""Shared stdlib-only deployment policy and private network lease."""

import dataclasses
import hashlib
import ipaddress
import json
import math
import os
import re
import stat
import tempfile
import time
import uuid
from pathlib import Path

LEASE_SECONDS = 15
PRIVATE_NETWORKS = tuple(
    ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def boottime():
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_field")
        result[key] = value
    return result


def private_json(path, limit=16384):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("private_regular_file_required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("private_input_too_large")
        return json.loads(data, object_pairs_hook=unique)
    finally:
        os.close(fd)


def write_private(path, value):
    path = Path(path)
    parent = path.parent
    info = parent.stat()
    if (
        parent.is_symlink()
        or not parent.is_dir()
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise ValueError("private_parent_required")
    fd, temporary = tempfile.mkstemp(prefix=".lan-", dir=parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, allow_nan=False, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclasses.dataclass(frozen=True)
class LanPolicy:
    interface: str
    address: str
    network: str
    connection_uuid: str
    ssid_sha256: str
    firewall_zone: str
    firewall_sha256: str
    hostname: str
    image: str
    devices: list[str]
    schema_version: int = 1
    device_per_minute: int = 6
    device_burst: int = 2
    edge_per_minute: int = 120
    edge_burst: int = 20

    def __post_init__(self):
        for field, pattern in (
            ("interface", r"[a-zA-Z0-9_.-]{1,15}"),
            ("firewall_zone", r"[a-zA-Z0-9_-]{1,32}"),
            ("ssid_sha256", r"[0-9a-f]{64}"),
            ("firewall_sha256", r"[0-9a-f]{64}"),
            ("image", r"sha256:[0-9a-f]{64}"),
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValueError("invalid_policy_field")
        if (
            not isinstance(self.connection_uuid, str)
            or str(uuid.UUID(self.connection_uuid)) != self.connection_uuid
        ):
            raise ValueError("canonical_connection_uuid_required")
        if (
            not isinstance(self.hostname, str)
            or len(self.hostname) > 128
            or "." not in self.hostname
            or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in self.hostname.split(".")
            )
        ):
            raise ValueError("stable_dns_hostname_required")
        if not isinstance(self.address, str) or not isinstance(self.network, str):
            raise ValueError("ipv4_strings_required")
        address = ipaddress.IPv4Address(self.address)
        network = ipaddress.IPv4Network(self.network, strict=True)
        if (
            not 16 <= network.prefixlen <= 30
            or not any(network.subnet_of(n) for n in PRIVATE_NETWORKS)
            or address not in network
            or address in (network.network_address, network.broadcast_address)
        ):
            raise ValueError("specific_private_lan_required")
        if (
            type(self.devices) is not list
            or not 1 <= len(self.devices) <= 16
            or len(set(self.devices)) != len(self.devices)
            or any(
                not isinstance(n, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", n)
                for n in self.devices
            )
        ):
            raise ValueError("bounded_configured_devices_required")
        for field, low, high in (
            ("schema_version", 1, 1),
            ("device_per_minute", 1, 60),
            ("device_burst", 1, 10),
            ("edge_per_minute", 10, 600),
            ("edge_burst", 1, 100),
        ):
            value = getattr(self, field)
            if type(value) is not int or not low <= value <= high:
                raise ValueError("policy_number_range")

    @classmethod
    def load(cls, path):
        return cls(**private_json(path))

    def fingerprint(self):
        return hashlib.sha256(
            json.dumps(dataclasses.asdict(self), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def rich_rule(self):
        return f'rule family="ipv4" source address="{self.network}" destination address="{self.address}/32" port port="8443" protocol="tcp" accept'


def lease_valid(path, policy, clock=boottime):
    try:
        value = private_json(path, 2048)
        observed = value["observed_boot_seconds"]
        now = clock()
        return (
            value["schema_version"] == 1
            and value["allowed"] is True
            and value["policy_sha256"] == policy.fingerprint()
            and type(observed) in (float, int)
            and math.isfinite(observed)
            and 0 <= now - observed < LEASE_SECONDS
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False
