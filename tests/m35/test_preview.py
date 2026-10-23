"""Offline proposal: fixtures, semantic state, rendering, BOOT and v1 boundary."""

import json
from copy import deepcopy
from itertools import product
from pathlib import Path

import preview
import pytest
from model import STATES, VIEWS, Navigation, aggregate, node_state, page, validate

ROOT = Path(__file__).resolve().parents[2]


def fixture(name="global"):
    return json.loads((ROOT / "tests/m35/fixtures" / (name + ".json")).read_text())


@pytest.mark.parametrize("view", VIEWS)
def test_eight_views_are_monochrome_deterministic_and_different(view):
    data = fixture(view)
    frame = preview.render(data, view)
    assert len(frame) == 5000
    assert frame == preview.render(data, view)
    assert b"\x00" in frame and b"\xff" in frame
    assert len(preview.codec.png_pixels(preview.codec.png(preview.pbm(frame)))) == 5200


def test_checked_visual_references_and_eight_unique_pages():
    assert preview.run(True) == 13
    frames = {preview.render(fixture(view), view) for view in VIEWS}
    assert len(frames) == 8


def test_unchanged_age_bucket_produces_same_frame_for_diff():
    data = fixture("node")
    before = preview.render(data, "node")
    data["now"] += 1
    assert preview.render(data, "node") == before


def test_empty_work_is_unknown_without_invented_nodes():
    title, state, lines = page(fixture("work"), "work")
    assert title == "SITIO TRABAJO" and state == "UNKNOWN"
    assert "SIN NODOS INCORPORADOS" in lines


@pytest.mark.parametrize(
    "age,expected", [(179, "HEALTHY"), (180, "UNKNOWN"), (359, "UNKNOWN"), (360, "OFFLINE")]
)
def test_exact_expiry_boundaries(age, expected):
    data = fixture()
    node = data["nodes"][0]
    node["collected_at"] = data["now"] - age
    assert node_state(node, data) == expected


def test_stale_node_never_renders_cpu_ram_disk_or_temperature_as_current():
    data = fixture("stale")
    _, status, lines = page(data, "node")
    assert status == "OFFLINE"
    assert "SIN METRICAS ACTUALES" in lines
    assert not any("CPU " in line or "DISCO " in line or "RAM " in line for line in lines)


def test_transport_failure_is_distinct_from_remote_node_failure():
    data = fixture("gateway-offline")
    assert node_state(data["nodes"][0], data) == "HEALTHY"
    _, status, lines = page(data, "global")
    assert status == "OFFLINE" and "GATEWAY NO DISPONIBLE" in lines
    assert "SALUD REMOTA NO VERIFICADA" in lines


def test_clock_untrusted_or_future_sample_cannot_display_live_metrics():
    data = fixture("clock-unknown")
    assert page(data, "node")[1] == "UNKNOWN"
    data["clock_trusted"] = True
    data["nodes"][0]["collected_at"] = data["now"] + 1
    assert node_state(data["nodes"][0], data) == "UNKNOWN"


def test_optional_cpu_temperature_absent_is_not_invented():
    data = fixture("node")
    data["nodes"][0]["temperature"] = None
    assert "TEMP CPU N/A" in page(data, "node")[2]


def test_partial_required_metric_is_unknown():
    data = fixture()
    data["nodes"][0]["ram"] = None
    assert node_state(data["nodes"][0], data) == "UNKNOWN"


def test_alerts_prioritize_critical_before_warning():
    _, status, lines = page(fixture("alerts"), "alerts")
    assert status == "CRITICAL" and lines[0] == "NAS DEMO CRITICAL"
    assert lines[2] == "MOVIL DEMO WARNING"


@pytest.mark.parametrize("missing", [True, False])
def test_local_environment_missing_crc_or_age_has_no_fake_value(missing):
    data = fixture("ambient-missing") if missing else fixture("ambient")
    if not missing:
        data["environment"]["crc_ok"] = False
    assert page(data, "ambient")[1] == "SIN MUESTRA"
    assert page(data, "ambient")[2] == ["SHTC3 SIN LECTURA VALIDA", "SIN VALORES ACTUALES"]


def test_local_environment_is_not_remote_cpu_temperature():
    data = fixture("ambient")
    lines = page(data, "ambient")[2]
    assert "TEMPERATURA 24.5 C" in lines
    assert "NO ES TEMPERATURA DE CPU" in lines


@pytest.mark.parametrize(
    "field,value", [("cpu", -1), ("ram", 101), ("disk", float("nan")), ("temperature", 130)]
)
def test_metric_range_and_finite_bounds(field, value):
    data = fixture()
    data["nodes"][0][field] = value
    with pytest.raises(ValueError):
        validate(data)


def test_bounded_synthetic_source_rejects_real_or_unknown_fields():
    for transform in (
        lambda d: d.update(synthetic=False),
        lambda d: d.update(token="must-not-be-here"),
        lambda d: d["nodes"].append(deepcopy(d["nodes"][0])),
    ):
        data = fixture()
        transform(data)
        with pytest.raises(ValueError):
            validate(data)


def press(nav, start, duration):
    nav.sample("BOOT", True, start)
    nav.sample("BOOT", True, start + 30)
    nav.sample("BOOT", False, start + duration)
    return nav.sample("BOOT", False, start + duration + 30)


def test_short_cycles_eight_views_long_returns_home_without_short_event():
    nav = Navigation()
    for i in range(8):
        assert press(nav, i * 200, 100) == "next"
        assert nav.view == (i + 1) % 8
    nav.view = 4
    assert press(nav, 2000, 1500) == "home" and nav.view == 0


def test_boot_held_at_wake_must_release_before_navigation():
    nav = Navigation()
    nav.wake(True, 0)
    assert nav.sample("BOOT", False, 100) is None
    assert nav.sample("BOOT", False, 130) is None
    assert nav.view == 0
    assert press(nav, 200, 100) == "next"


def test_bounce_sleep_and_pwr_do_not_navigate_or_change_power():
    nav = Navigation()
    nav.sample("BOOT", True, 10)
    nav.sample("BOOT", False, 20)
    assert nav.sample("BOOT", False, 50) is None
    assert nav.sample("PWR", True, 100) is None
    assert nav.sample("PWR", False, 2000) is None
    assert nav.sample("BOOT", True, 2100, awake=False) is None
    assert nav.view == 0


def test_design_aggregation_matches_existing_core_precedence():
    from infrabadge_gateway.distributed.core import aggregate as core_aggregate

    assert aggregate([]) == core_aggregate([])
    for states in product(STATES, repeat=3):
        assert aggregate(states) == core_aggregate(states)


def test_gpio_ledger_matches_validated_hal_without_allocating_new_pins():
    import re

    ledger = json.loads((ROOT / "docs/m35-hardware.json").read_text())
    header = (ROOT / "components/hal_waveshare_v2/include/ib_board_pins.h").read_text()
    macros = {
        key: int(value)
        for key, value in re.findall(r"#define (IB_PIN_[A-Z0-9_]+) ([0-9]+)", header)
    }
    matched = {row["hal_macro"]: row["gpio"][0] for row in ledger["gpio"] if row["hal_macro"]}
    assert matched == macros
    assert ledger["physical_new_peripherals_validated"] is False


def test_pinned_schematic_matches_existing_upstream_lock():
    ledger = json.loads((ROOT / "docs/m35-hardware.json").read_text())
    upstream = json.loads((ROOT / "docs/upstream.json").read_text())
    assert ledger["reference_commit"] == upstream["board_reference"]["commit"]
    schematic = next(s for s in ledger["sources"] if s["path"].endswith("Schematic.pdf"))
    assert schematic["sha256"] == upstream["schematic"]["sha256"]


def test_j1_usb_i2c_and_led_are_not_free_gpio():
    ledger = json.loads((ROOT / "docs/m35-hardware.json").read_text())
    candidates = next(r["gpio"] for r in ledger["gpio"] if r["name"] == "expansion-candidates")
    assert candidates == [1, 2]
    assert ledger["j1"]["8"] == "GPIO48 / SCL"
    assert ledger["j1"]["10"] == "GPIO47 / SDA"
    assert "LED_G" in ledger["j1"]["5"]


def test_expired_local_environment_is_not_a_current_reading():
    data = fixture("ambient")
    data["environment"]["collected_at"] = data["now"] - 180
    assert page(data, "ambient")[1] == "SIN MUESTRA"
