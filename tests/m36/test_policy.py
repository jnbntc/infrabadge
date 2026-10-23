"""Validate the production C config boundary with deterministic synthetic inputs."""

import copy
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fixtures import bundle

ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path(os.environ.get("IB_M36_NATIVE", ROOT / "results/m36-native/policy"))


def validate(value):
    if not NATIVE.is_file():
        pytest.skip("Native policy executable built by SDK job, unavailable on this runner")
    data = value if isinstance(value, bytes) else json.dumps(value, separators=(",", ":")).encode()
    result = subprocess.run([str(NATIVE), "--validate"], input=data, capture_output=True)
    assert not result.stdout and not result.stderr  # config/credentials never printed
    assert result.returncode in (0, 2)
    return result.returncode == 0


def test_valid_enabled_disabled_and_single_route():
    config = bundle()
    assert validate(config)
    config["policy"]["night_mode_enabled"] = False
    assert validate(config)
    config["routes"] = config["routes"][:1]
    config["bindings"] = config["bindings"][:1]
    assert validate(config)


@pytest.mark.parametrize(
    "field,value",
    [
        ("night_start", "24:00"),
        ("night_start", "8:00"),
        ("night_start", "08:00"),  # empty window
        ("night_end", "08:60"),
        ("night_mode_enabled", 1),
        ("timezone", "UTC"),
        ("timezone", "EST5EDT"),
        ("extra", True),
    ],
)
def test_policy_rejects_ambiguous_or_unsupported_values(field, value):
    config = bundle()
    config["policy"][field] = value
    assert not validate(config)


@pytest.mark.parametrize(
    "kind",
    [
        "same_ssid",
        "same_url",
        "different_device",
        "binding",
        "duplicate_site",
        "seed",
        "cleartext",
        "timeout",
        "extra",
        "third",
    ],
)
def test_route_and_credential_validation(kind):
    config = bundle()
    a, b = config["bindings"]
    if kind == "same_ssid":
        b["ssid"] = a["ssid"]
    elif kind == "same_url":
        b["gateway_url"] = a["gateway_url"]
    elif kind == "different_device":
        b["device_id"] = "other"
    elif kind == "binding":
        config["routes"][1]["binding"] = 0
    elif kind == "duplicate_site":
        config["routes"][1]["site_id"] = "home"
    elif kind == "seed":
        b["seed_utc"] += 1
    elif kind == "cleartext":
        b["gateway_url"] = "http://work.test:8443"
    elif kind == "timeout":
        b["wifi_timeout_ms"] = 20000
    elif kind == "extra":
        config["routes"][0]["execute"] = "ignored?"
    else:
        config["routes"].append(copy.deepcopy(config["routes"][0]))
        config["bindings"].append(copy.deepcopy(a))
    assert not validate(config)


def test_duplicate_keys_nul_unicode_depth_size():
    data = json.dumps(bundle(), separators=(",", ":")).encode()
    assert not validate(
        data.replace(b'"schema_version":1,', b'"schema_version":1,"schema_version":1,', 1)
    )
    assert not validate(data + b"\0")
    assert not validate(data.replace(b"home-demo", b"home\\u0000-demo"))
    assert not validate(b"[" * 20 + b"]" * 20)
    assert not validate(b" " * 11001)


def test_fixed_zone_matches_iana_current_horizon():
    # The supported policy deliberately does not accept arbitrary POSIX TZ code.
    for year in (2026, 2027, 2030):
        for month in (1, 7, 12):
            stamp = datetime(year, month, 1, 11, tzinfo=timezone.utc)
            assert stamp.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).hour == 8
