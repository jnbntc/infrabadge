#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v idf.py >/dev/null 2>&1 && [[ ${1:-} != --inside ]]; then
    exec distrobox enter --name iot-dev -- /usr/local/bin/idf-env bash "$project_root/tools/build.sh" --inside "$@"
fi
if [[ ${1:-} == --inside ]]; then shift; fi
profile=${1:-all}
case "$profile" in display|sensors|sleep|all) ;; *) echo 'Uso: tools/build.sh [display|sensors|sleep|all]' >&2; exit 2 ;; esac
cd -- "$project_root"
mkdir -p results
result_dir=$(mktemp -d "$project_root/results/m0-build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
finish() {
    local code=$?
    trap - EXIT
    python3 - "$result_dir" "$code" "$profile" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
(out / 'result.json').write_text(json.dumps({'status': 'passed' if sys.argv[2] == '0' else 'failed',
    'exit_code': int(sys.argv[2]), 'requested_profile': sys.argv[3],
    'flash_performed': False, 'hardware_io_performed': False}, indent=2) + '\n')
print(f'Resultados: {out}')
PY
    exit "$code"
}
trap finish EXIT
{
    [[ $(idf.py --version) == 'ESP-IDF v5.5.5' ]] || { echo 'Se requiere ESP-IDF v5.5.5' >&2; exit 1; }
    [[ $(git -C "$IDF_PATH" rev-parse HEAD) == b774170ff46c393eeb5e495ea37936038d3f4f4f ]] || {
        echo 'El commit ESP-IDF no coincide con la versión fijada' >&2; exit 1;
    }
    bash tools/test.sh
    profiles=("$profile")
    if [[ $profile == all ]]; then profiles=(display sensors sleep); fi
    for mode in "${profiles[@]}"; do
        build_dir="$project_root/build-m0/$mode"
        mkdir -p "$build_dir"
        idf.py -B "$build_dir" -DIDF_TARGET=esp32s3 -DSDKCONFIG="$build_dir/sdkconfig" \
            -DSDKCONFIG_DEFAULTS="$project_root/sdkconfig.defaults;$project_root/config/$mode.defaults" build
        python3 tools/verify_build.py --profile "$mode" --build "$build_dir" --output "$result_dir/$mode.json"
    done
} 2>&1 | tee "$result_dir/build.log"
