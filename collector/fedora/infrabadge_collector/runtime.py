"""Private collector-owned state/config I/O. Acquisition is kept separate."""

import json
import math
import os
import re
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def private_bytes(path, maximum):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("private_file_permissions")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            value = stream.read(maximum + 1)
        if len(value) > maximum:
            raise ValueError("private_file_size")
        return value
    finally:
        os.close(fd)


def load_config(path):
    value = json.loads(private_bytes(path, 8192))
    required = {
        "node_id",
        "gateway_url",
        "ca_file",
        "mount_path",
        "mount_id",
        "state_file",
        "interval_seconds",
        "timeout_seconds",
    }
    if (
        not isinstance(value, dict)
        or not required <= set(value)
        or set(value) - required - {"delivery_attempts"}
    ):
        raise ValueError("config_fields")
    if not isinstance(value["node_id"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,31}", value["node_id"]
    ):
        raise ValueError("logical_node")
    if not isinstance(value["mount_id"], str) or not re.fullmatch(
        r"[A-Z0-9_-]{1,12}", value["mount_id"]
    ):
        raise ValueError("logical_mount")
    for key in ("ca_file", "mount_path", "state_file"):
        if not isinstance(value[key], str) or not Path(value[key]).is_absolute():
            raise ValueError("absolute_local_path")
    url = urlsplit(value["gateway_url"])
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
        or not 1 <= (url.port or 443) <= 65535
    ):
        raise ValueError("https_origin_required")
    for key, low, high in (("interval_seconds", 10, 3600), ("timeout_seconds", 1, 15)):
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise ValueError("config_interval")
    if (
        type(value.get("delivery_attempts", 1)) is not int
        or not 1 <= value.get("delivery_attempts", 1) <= 2
    ):
        raise ValueError("bounded delivery attempts required")
    return value


def load_baseline(path):
    try:
        value = json.loads(private_bytes(path, 4096))
        if not isinstance(value, dict) or set(value) != {"ticks", "logical_cpus", "uptime"}:
            return None
        if (
            type(value["logical_cpus"]) is not int
            or not 1 <= value["logical_cpus"] <= 8192
            or not isinstance(value["ticks"], list)
            or len(value["ticks"]) != 8
            or any(type(v) is not int or not 0 <= v <= 2**64 for v in value["ticks"])
            or type(value["uptime"]) not in (int, float)
            or not math.isfinite(value["uptime"])
            or not 0 <= value["uptime"] <= 1e12
        ):
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def save_baseline(path, value):
    path = Path(path)
    if not path.parent.is_dir() or path.parent.stat().st_mode & 0o077:
        raise ValueError("private_state_directory_required")
    fd, temporary = tempfile.mkstemp(prefix=".cpu-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, allow_nan=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def require_host():
    if os.geteuid() == 0:
        raise ValueError("non_root_host_required")
    if (
        Path("/run/.containerenv").exists()
        or Path("/.dockerenv").exists()
        or os.environ.get("container")
    ):
        raise ValueError("host_namespace_required")
