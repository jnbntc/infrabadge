#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
files=(gateway/infrabadge_gateway/distributed gateway/tests/test_m32*.py tools/m32 collector/fedora gateway/infrabadge_gateway/{app,base,metrics,models}.py
       gateway/tests/test_m3.py gateway/tests/test_m3_https.py gateway/tests/test_m3_observer.py gateway/tests/test_m3_session.py tools/m3 tools/simulate_m3.py)
ruff check "${files[@]}"
ruff format --check "${files[@]}"
