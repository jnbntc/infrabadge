#!/usr/bin/env python3
"""Deterministic examples of REAL-source wire semantics, with synthetic metrics."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gateway"))
from infrabadge_gateway.metrics import Collector, Evaluation, Metrics


def generate():
    collector = Collector(token_sha256=["0" * 64], display_name="WORKSTATION")
    for name, state, cpu, free, temp in [
        ("healthy", "HEALTHY", 12.0, 60, 48.5),
        ("warning", "WARNING", 88.0, 60, 65.0),
        ("critical", "CRITICAL", 98.0, 4, 75.0),
        ("no-temperature", "HEALTHY", 8.0, 60, None),
    ]:
        evaluation = Evaluation()
        for i in range(3):
            data = dict(
                schema_version=1,
                node_id="workstation",
                collector_version="0.3.0",
                collected_at=1800000000 + i * 60,
                cpu=dict(usage_percent=cpu, logical_cpus=8, load_average=[1.0, 1.0, 1.0]),
                memory=dict(
                    total_bytes=10000,
                    available_bytes=free * 100,
                    used_bytes=(100 - free) * 100,
                    used_percent=float(100 - free),
                    available_estimated=False,
                ),
                disk=dict(
                    mount_id="HOME", total_bytes=10000, available_bytes=6000, used_percent=40.0
                ),
                temperature=dict(celsius=temp, sensor="cpu_package") if temp is not None else None,
                uptime_seconds=1000.0 + i * 60,
                errors=[],
            )
            evaluation.ingest(Metrics.model_validate(data), collector.policy)
        snapshot = evaluation.snapshot("badge-lab", collector, 1800000120, 1)
        assert snapshot.status == state
        yield name, snapshot
        if name == "healthy":
            yield "stale", evaluation.snapshot("badge-lab", collector, 1800000300, 2)
    yield "missing", Evaluation().snapshot("badge-lab", collector, 1800000120, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, snapshot in generate():
        path = ROOT / "protocol/m3-fixtures" / (name + ".json")
        content = json.dumps(snapshot.model_dump(), sort_keys=True, separators=(",", ":")) + "\n"
        if args.check:
            assert path.read_text() == content, "M3 fixture differs: " + name
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print("Six SYNTHETIC M3 wire fixtures verified" if args.check else "M3 fixtures generated")


if __name__ == "__main__":
    main()
