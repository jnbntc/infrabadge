"""Deterministic software-only v2 topology and samples; no private inventory."""

import json
from pathlib import Path

from infrabadge_gateway.distributed.config import CoreConfig
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.presentation import project
from infrabadge_gateway.distributed.store import Store
from m32_fixtures import NOW, configuration, identity, sample


def config():
    raw = configuration().model_dump()
    raw["sites"]["alpha"]["display_name"] = "CASA"
    raw["sites"]["beta"]["display_name"] = "MOVIL"
    raw["sites"]["work"] = dict(display_name="TRABAJO", enabled=False)
    raw["nodes"]["c"] = dict(
        site_id="alpha", display_name="NODE_C", node_type="gateway", enabled=True
    )
    raw["collectors"]["c"] = identity("s-reader")
    del raw["readers"]["read-b"]
    raw["devices"]["display-a"].update(site_ids=["alpha", "beta", "work"], presentation_v2=True)
    return CoreConfig.model_validate(raw)


def body(folder, scenario="healthy"):
    store = Store(folder / "core.db")
    core = Core(config(), store)
    try:
        for node in () if scenario == "never" else ("a", "b", "c"):
            m = sample(
                node=node,
                available=2
                if scenario == "critical" and node == "a"
                else 10
                if scenario == "warning" and node == "a"
                else 70,
            )
            if scenario == "missing" and node == "a":
                raw = m.model_dump()
                raw.update(cpu=None, memory=None, disk=None, temperature=None)
                m = type(m).model_validate(raw)
            core.ingest(node, m, NOW)
        when = NOW + 181 if scenario == "stale" else NOW + 601 if scenario == "offline" else NOW
        return project(core, "display-a", when)
    finally:
        store.close()


def write(folder, output):
    # The caller supplies separate private temporary stores for each scenario.
    output.write_bytes(body(folder))


if __name__ == "__main__":
    import argparse
    import tempfile

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    for scenario in ("healthy", "warning", "critical", "missing", "stale", "offline", "never"):
        with tempfile.TemporaryDirectory() as temporary:
            content = body(Path(temporary), scenario)
        target = root / "tests/fixtures/m35-wire" / (scenario + ".json")
        if args.check:
            assert json.loads(target.read_bytes()) == json.loads(content), scenario
        else:
            target.write_bytes(content + b"\n")
    print("PASS: seven synthetic Core v2 fixtures")
