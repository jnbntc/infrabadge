#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v idf.py >/dev/null 2>&1 && [[ ${1:-} != --inside ]]; then
    exec distrobox enter --name iot-dev -- /usr/local/bin/idf-env bash "$project_root/tools/build-m1.sh" --inside "$@"
fi
if [[ ${1:-} == --inside ]]; then shift; fi
if [[ ${1:-} == --all ]]; then bash "$project_root/tools/build.sh" all; shift; fi
[[ $# == 0 ]] || { echo 'Uso: tools/build-m1.sh [--all]' >&2; exit 2; }
cd -- "$project_root"
mkdir -p results
result_dir=$(mktemp -d "$project_root/results/m1-build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
finish() {
    local code=$?
    trap - EXIT
    python3 - "$result_dir" "$code" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
(out / 'result.json').write_text(json.dumps({'status': 'passed' if sys.argv[2] == '0' else 'failed',
    'exit_code': int(sys.argv[2]), 'profile': 'ui', 'flash_performed': False,
    'hardware_io_performed': False}, indent=2) + '\n')
print(f'Resultados: {out}')
PY
    exit "$code"
}
trap finish EXIT
{
    [[ $(idf.py --version) == 'ESP-IDF v5.5.5' ]]
    [[ $(git -C "$IDF_PATH" rev-parse HEAD) == b774170ff46c393eeb5e495ea37936038d3f4f4f ]]
    bash tools/test.sh
    build_dir="$project_root/build-m1/ui"
    mkdir -p "$build_dir"
    idf.py -B "$build_dir" -DIDF_TARGET=esp32s3 -DSDKCONFIG="$build_dir/sdkconfig" \
        -DSDKCONFIG_DEFAULTS="$project_root/sdkconfig.defaults;$project_root/config/ui.defaults" build
    python3 tools/verify_build.py --profile ui --build "$build_dir" --output "$result_dir/ui.json"
} 2>&1 | tee "$result_dir/build.log"
