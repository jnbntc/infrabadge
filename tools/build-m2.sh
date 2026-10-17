#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if ! command -v idf.py >/dev/null 2>&1 && [[ ${1:-} != --inside ]]; then
    exec distrobox enter --name iot-dev -- /usr/local/bin/idf-env bash "$project_root/tools/build-m2.sh" --inside "$@"
fi
if [[ ${1:-} == --inside ]]; then shift; fi
if [[ ${1:-} == --all ]]; then bash "$project_root/tools/build-timer.sh" --all; shift; fi
[[ $# == 0 ]] || { echo 'Uso: tools/build-m2.sh [--all]' >&2; exit 2; }
cd -- "$project_root"
mkdir -p results
result_dir=$(mktemp -d "$project_root/results/m2-build-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
finish() {
    local code=$?; trap - EXIT
    python3 - "$result_dir" "$code" <<'PY'
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);(out/'result.json').write_text(json.dumps({'status':'passed' if sys.argv[2]=='0' else 'failed',
    'exit_code':int(sys.argv[2]),'profile':'connectivity','flash_performed':False,'hardware_io_performed':False},indent=2)+'\n')
print(f'Resultados: {out}')
PY
    exit "$code"
}
trap finish EXIT
{
    [[ $(idf.py --version) == 'ESP-IDF v5.5.5' ]]
    [[ $(git -C "$IDF_PATH" rev-parse HEAD) == b774170ff46c393eeb5e495ea37936038d3f4f4f ]]
    IB_SANITIZE=1 bash tools/test-m2.sh
    build_dir="$project_root/build-m2/connectivity"
    mkdir -p "$build_dir"
    # This directory is generated exclusively by this fixed profile. Regenerate its
    # sdkconfig when defaults change; IDF otherwise preserves stale default values.
    python3 - "$build_dir" <<'PYCONFIG'
import hashlib,sys
from pathlib import Path
folder=Path(sys.argv[1]);stamp=folder/'.defaults-sha256'
digest=hashlib.sha256(Path('sdkconfig.defaults').read_bytes()+Path('config/m2.defaults').read_bytes()).hexdigest()
if not stamp.exists() or stamp.read_text()!=digest:
    (folder/'sdkconfig').unlink(missing_ok=True)
    stamp.write_text(digest)
PYCONFIG
    idf.py -B "$build_dir" -DIB_BUILD_M2=ON -DIDF_TARGET=esp32s3 -DSDKCONFIG="$build_dir/sdkconfig" \
        -DSDKCONFIG_DEFAULTS="$project_root/sdkconfig.defaults;$project_root/config/m2.defaults" build
    python3 tools/verify_build.py --profile connectivity --build "$build_dir" --output "$result_dir/connectivity.json"
} 2>&1 | tee "$result_dir/build.log"
