"""Bounded read-only acquisition. Never reads credentials or host identifiers."""
import math
import os
import re
from pathlib import Path


def read_text(path, limit=262144):
    with Path(path).open("r", encoding="ascii") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError("source_too_large")
    return value


def parse_stat(text):
    lines = text.splitlines()
    aggregate = next(line.split()[1:] for line in lines if line.startswith("cpu "))
    if len(aggregate) < 8:
        raise ValueError("cpu_fields")
    ticks = tuple(int(value) for value in aggregate[:8])
    cpus = sum(bool(re.match(r"^cpu[0-9]+\s", line)) for line in lines)
    if any(value < 0 for value in ticks) or not 1 <= cpus <= 8192:
        raise ValueError("cpu_values")
    # guest/guest_nice are already included in user/nice: do not count twice.
    return {"ticks": list(ticks), "logical_cpus": cpus}


def cpu_delta(current, previous, uptime, max_gap=180):
    if not previous or uptime is None:
        return None
    if (current["logical_cpus"] != previous.get("logical_cpus")
            or not 0 < uptime - previous.get("uptime", uptime) <= max_gap):
        return None
    old = previous.get("ticks", [])
    if len(old) != 8:
        return None
    delta = [a - b for a, b in zip(current["ticks"], old)]
    # Linux iowait can decrease. Reject that interval instead of inventing load.
    if any(value < 0 for value in delta) or sum(delta) <= 0:
        return None
    idle = delta[3] + delta[4]
    return round(100 * (sum(delta) - idle) / sum(delta), 2)


def parse_meminfo(text):
    fields = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        if key in {"MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached", "SReclaimable", "Shmem"}:
            parts = value.split()
            if key in fields or len(parts) != 2 or parts[1] != "kB":
                raise ValueError("memory_fields")
            fields[key] = int(parts[0]) * 1024
    total = fields["MemTotal"]
    estimated = "MemAvailable" not in fields
    available = (fields["MemFree"] + fields["Buffers"] + fields["Cached"]
                 + fields.get("SReclaimable", 0) - fields.get("Shmem", 0)) if estimated else fields["MemAvailable"]
    if estimated:
        available = min(total, max(0, available))
    if total <= 0 or available < 0 or available > total or any(v < 0 for v in fields.values()):
        raise ValueError("memory_values")
    return {"total_bytes": total, "available_bytes": available, "used_bytes": total - available,
            "used_percent": round(100 * (total - available) / total, 2), "available_estimated": estimated}


def disk_usage(path, mount_id, statvfs=os.statvfs):
    value = statvfs(path)
    block = value.f_frsize or value.f_bsize
    total = value.f_blocks * block
    available = max(0, value.f_bavail) * block
    if total <= 0 or not 0 <= available <= total:
        raise ValueError("disk_values")
    return {"mount_id": mount_id, "total_bytes": total, "available_bytes": available,
            "used_percent": round(100 * (total - available) / total, 2)}


def parse_uptime(text):
    value = float(text.split()[0])
    if not math.isfinite(value) or not 0 <= value <= 1e12:
        raise ValueError("uptime_values")
    return value


def parse_load(text):
    values = [float(value) for value in text.split()[:3]]
    if len(values) != 3 or any(not math.isfinite(v) or not 0 <= v <= 1e6 for v in values):
        raise ValueError("load_values")
    return values


def cpu_temperature(hwmon_root):
    candidates = []
    for chip in sorted(Path(hwmon_root).glob("hwmon[0-9]*"))[:64]:
        try:
            driver = read_text(chip / "name", 128).strip()
            if driver not in ("coretemp", "k10temp", "zenpower"):
                continue
            for channel in sorted(chip.glob("temp[0-9]*_input"))[:64]:
                stem = channel.name[:-6]
                try:
                    label = read_text(chip / (stem + "_label"), 128).strip()
                    if driver == "coretemp" and re.fullmatch(r"Package id [0-9]+", label):
                        priority, sensor = 0, "cpu_package"
                    elif driver == "coretemp" and re.fullmatch(r"Core [0-9]+", label):
                        priority, sensor = 1, "cpu_core"
                    elif driver in ("k10temp", "zenpower") and label == "Tdie":
                        priority, sensor = 0, "cpu_die"
                    else:
                        continue  # Tctl/ACPI/GPU must not be guessed to be CPU die.
                    fault = chip / (stem + "_fault")
                    enabled = chip / (stem + "_enable")
                    if fault.exists() and read_text(fault, 16).strip() != "0":
                        continue
                    if enabled.exists() and read_text(enabled, 16).strip() == "0":
                        continue
                    temperature = int(read_text(channel, 32).strip()) / 1000
                    if -40 <= temperature <= 150:
                        candidates.append((priority, temperature, sensor))
                except (OSError, ValueError, UnicodeError):
                    continue
        except (OSError, ValueError, UnicodeError):
            continue
    if not candidates:
        return None
    priority = min(item[0] for item in candidates)
    _, temperature, sensor = max((item for item in candidates if item[0] == priority), key=lambda item: item[1])
    return {"celsius": round(temperature, 3), "sensor": sensor}


def acquire(node_id, mount_path, mount_id, previous=None, proc_root=Path("/proc"),
            hwmon_root=Path("/sys/class/hwmon"), now=None, max_gap=180):
    import time
    from . import __version__
    errors = []

    def attempt(code, function):
        try:
            return function()
        except (OSError, ValueError, KeyError, StopIteration, UnicodeError):
            errors.append(code)
            return None

    uptime = attempt("uptime_unavailable", lambda: parse_uptime(read_text(proc_root / "uptime", 128)))
    counters = attempt("cpu_unavailable", lambda: parse_stat(read_text(proc_root / "stat")))
    load = attempt("load_unavailable", lambda: parse_load(read_text(proc_root / "loadavg", 256)))
    cpu = None
    baseline = None
    if counters:
        usage = cpu_delta(counters, previous, uptime, max_gap)
        if usage is None:
            errors.append("cpu_warmup")
        cpu = {"usage_percent": usage, "logical_cpus": counters["logical_cpus"], "load_average": load}
        if uptime is not None:
            baseline = dict(counters, uptime=uptime)
    memory = attempt("memory_unavailable", lambda: parse_meminfo(read_text(proc_root / "meminfo")))
    disk = attempt("disk_unavailable", lambda: disk_usage(mount_path, mount_id))
    temperature = attempt("temperature_unavailable", lambda: cpu_temperature(hwmon_root))
    if temperature is None and "temperature_unavailable" not in errors:
        errors.append("temperature_unavailable")
    stamp = int(time.time() if now is None else now)
    if not 1577836800 <= stamp <= 4102444800:
        raise ValueError("utc_outside_protocol")
    return {"schema_version": 1, "node_id": node_id, "collector_version": __version__, "collected_at": stamp,
            "cpu": cpu, "memory": memory, "disk": disk, "temperature": temperature,
            "uptime_seconds": uptime, "errors": errors}, baseline
