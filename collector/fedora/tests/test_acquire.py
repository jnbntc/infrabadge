from pathlib import Path
from types import SimpleNamespace

import pytest
from infrabadge_collector.acquire import (
    acquire,
    cpu_delta,
    cpu_temperature,
    disk_usage,
    parse_load,
    parse_meminfo,
    parse_stat,
    parse_uptime,
)


def stat(values="100 20 30 400 50 5 5 0 30 10", cores=2):
    return "cpu " + values + "\n" + "".join(f"cpu{i} 1 0 0 2\n" for i in range(cores))


def test_cpu_delta_guest_idle_hotplug_and_reset():
    before = parse_stat(stat())
    assert sum(before["ticks"]) == 610  # No double-counting guest fields30/10.
    previous = dict(before, uptime=10)
    now = parse_stat(stat("150 20 30 440 60 5 5 0 80 10"))
    assert cpu_delta(now, previous, 70) == 50
    assert cpu_delta(now, None, 70) is None
    assert cpu_delta(now, previous, 9) is None
    assert cpu_delta(now, previous, 500) is None
    assert cpu_delta(parse_stat(stat(cores=3)), previous, 70) is None
    assert cpu_delta(parse_stat(stat("150 20 30 440 40 5 5 0")), previous, 70) is None
    assert cpu_delta(before, previous, 70) is None


@pytest.mark.parametrize("value", ["", "cpu 1 2\ncpu0 1", stat("-1 0 0 0 0 0 0 0"), stat(cores=0)])
def test_invalid_stat(value):
    with pytest.raises((ValueError, StopIteration)):
        parse_stat(value)


def test_memavailable_and_explicit_estimated_fallback():
    value = parse_meminfo("MemTotal: 1000 kB\nMemAvailable: 250 kB\n")
    assert value["used_percent"] == 75 and value["used_bytes"] == 750 * 1024
    assert value["available_estimated"] is False
    value = parse_meminfo(
        "MemTotal: 1000 kB\nMemFree: 100 kB\nBuffers: 50 kB\nCached: 200 kB\nSReclaimable: 50 kB\nShmem: 25 kB\n"
    )
    assert value["available_bytes"] == 375 * 1024 and value["available_estimated"] is True


@pytest.mark.parametrize(
    "value",
    [
        "MemTotal: 0 kB\nMemAvailable: 0 kB",
        "MemTotal: 10 kB\nMemAvailable: 20 kB",
        "MemTotal: 10 MB",
        "MemTotal: 10 kB",
    ],
)
def test_invalid_memory(value):
    with pytest.raises((ValueError, KeyError)):
        parse_meminfo(value)


def test_disk_uses_unprivileged_available_and_no_directory_walk():
    def source(path):
        assert path == "/configured/mount"
        return SimpleNamespace(f_frsize=4096, f_bsize=4096, f_blocks=100, f_bavail=10)

    value = disk_usage("/configured/mount", "DATA", source)
    assert value["available_bytes"] == 40960 and value["used_percent"] == 90
    assert value["mount_id"] == "DATA" and "path" not in value


def sensor(root, driver, label, number, name="hwmon0", **flags):
    chip = root / name
    chip.mkdir()
    (chip / "name").write_text(driver)
    (chip / "temp1_label").write_text(label)
    (chip / "temp1_input").write_text(str(number))
    for key, value in flags.items():
        (chip / ("temp1_" + key)).write_text(str(value))


def test_reliable_cpu_sensor_selection_and_absence(tmp_path):
    assert cpu_temperature(tmp_path) is None
    sensor(tmp_path, "acpitz", "thermal zone", 90000)
    assert cpu_temperature(tmp_path) is None
    sensor(tmp_path, "coretemp", "Core 0", 55000, "hwmon1")
    sensor(tmp_path, "coretemp", "Package id 0", 50000, "hwmon2")
    assert cpu_temperature(tmp_path) == {"celsius": 50.0, "sensor": "cpu_package"}
    sensor(tmp_path, "coretemp", "Package id 1", 70000, "hwmon3", fault=1)
    assert cpu_temperature(tmp_path)["celsius"] == 50


def test_amd_control_is_not_die_and_bad_sensor(tmp_path):
    sensor(tmp_path, "k10temp", "Tctl", 72000)
    assert cpu_temperature(tmp_path) is None
    sensor(tmp_path, "k10temp", "Tdie", 62500, "hwmon1")
    assert cpu_temperature(tmp_path) == {"celsius": 62.5, "sensor": "cpu_die"}
    (tmp_path / "hwmon1/temp1_input").write_text("999999999")
    assert cpu_temperature(tmp_path) is None


def test_uptime_load_and_utc_incomplete_sources(tmp_path):
    assert parse_uptime("123.45 99.9") == 123.45
    assert parse_load("1.0 0.5 0.25 1/200 4") == [1, 0.5, 0.25]
    for value in ("nan", "inf", "-1"):
        with pytest.raises(ValueError):
            parse_uptime(value)
    metrics, baseline = acquire(
        "workstation",
        str(tmp_path / "missing"),
        "HOME",
        proc_root=tmp_path,
        hwmon_root=tmp_path,
        now=1800000000,
    )
    assert (
        metrics["cpu"] is metrics["memory"] is metrics["disk"] is metrics["uptime_seconds"] is None
    )
    assert "cpu_unavailable" in metrics["errors"] and baseline is None
    assert metrics["collected_at"] == 1800000000 and "hostname" not in metrics
    with pytest.raises(ValueError):
        acquire(
            "workstation", str(tmp_path), "HOME", proc_root=tmp_path, hwmon_root=tmp_path, now=0
        )


def test_full_fixture_and_read_errors(tmp_path, monkeypatch):
    (tmp_path / "stat").write_text(stat())
    (tmp_path / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 700 kB")
    (tmp_path / "loadavg").write_text("0.1 0.2 0.3")
    (tmp_path / "uptime").write_text("100 20")
    value, baseline = acquire(
        "workstation",
        str(tmp_path),
        "HOME",
        proc_root=tmp_path,
        hwmon_root=tmp_path,
        now=1800000000,
    )
    assert value["cpu"]["logical_cpus"] == 2 and value["cpu"]["usage_percent"] is None
    assert baseline["uptime"] == 100 and value["memory"]["used_percent"] == 30
    original = Path.open

    def denied(path, *args, **kwargs):
        if path.name == "meminfo":
            raise PermissionError("must never be logged")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    partial, _ = acquire(
        "workstation",
        str(tmp_path),
        "HOME",
        proc_root=tmp_path,
        hwmon_root=tmp_path,
        now=1800000000,
    )
    assert partial["memory"] is None and "memory_unavailable" in partial["errors"]
