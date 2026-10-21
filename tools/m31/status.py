#!/usr/bin/env python3
"""Private local telemetry view; no network probe, token or raw metrics."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gateway"))
from infrabadge_gateway.lan_policy import LanPolicy, lease_valid, private_json
from infrabadge_gateway.lan_telemetry import view


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--telemetry", type=Path, required=True)
    args = parser.parse_args()
    try:
        state = view(private_json(args.telemetry, 8192), int(time.time()))
        state["network_guard_approved"] = lease_valid(args.lease, LanPolicy.load(args.policy))
        print(json.dumps(state))
    except Exception:
        raise SystemExit("Status unavailable; inspect private local files.") from None


if __name__ == "__main__":
    main()
