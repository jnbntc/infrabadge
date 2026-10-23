#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v idf.py >/dev/null 2>&1 && [[ ${1:-} != --inside ]]; then
    exec distrobox enter --name iot-dev -- /usr/local/bin/idf-env bash "$project_root/tools/build-m36.sh" --inside "$@"
fi
if [[ ${1:-} == --inside ]]; then shift; fi
if [[ ${1:-} == --all ]]; then bash "$project_root/tools/build-m35.sh" --all; shift; fi
[[ $# == 0 ]] || { echo 'Uso: tools/build-m36.sh [--all]' >&2; exit 2; }
cd -- "$project_root"
mkdir -p results
result_dir=$(mktemp -d "$project_root/results/m36-build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
echo "Resultados: $result_dir"
{
    [[ $(git -C "$IDF_PATH" rev-parse HEAD) == b774170ff46c393eeb5e495ea37936038d3f4f4f ]]
    IB_SANITIZE=1 bash tools/m36/test-native.sh
    build_dir="$project_root/build-m36/roaming";mkdir -p "$build_dir"
    idf.py -B "$build_dir" -DIB_BUILD_M2=ON -DIB_BUILD_M35=ON -DIB_BUILD_M36=ON -DIDF_TARGET=esp32s3 \
        -DSDKCONFIG="$build_dir/sdkconfig" \
        -DSDKCONFIG_DEFAULTS="$project_root/sdkconfig.defaults;$project_root/config/m36.defaults" build
    python3 tools/verify_build.py --profile roaming --build "$build_dir" --output "$result_dir/roaming.json"
    idf.py -B "$build_dir" size --format json > "$result_dir/memory.json"
} 2>&1 | tee "$result_dir/build.log"
