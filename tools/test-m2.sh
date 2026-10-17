#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
: "${IDF_PATH:?Ejecutar dentro del entorno ESP-IDF fijado}"
test "$(git -C "$IDF_PATH" rev-parse HEAD)" = b774170ff46c393eeb5e495ea37936038d3f4f4f
native_dir=$(mktemp -d "${TMPDIR:-/tmp}/infrabadge-m2-XXXXXX")
trap 'rm -rf -- "$native_dir"' EXIT
flags=(-std=c11 -O1 -g -UNDEBUG -Wall -Wextra -Werror)
if [[ ${IB_SANITIZE:-0} == 1 ]]; then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer); fi
"${CC:-cc}" "${flags[@]}" -I components/connectivity_core/include -I components/ui/include \
    -I "$IDF_PATH/components/json/cJSON" components/connectivity_core/snapshot.c \
    components/connectivity_core/cycle.c components/connectivity_core/http_limits.c components/connectivity_core/errors.c "$IDF_PATH/components/json/cJSON/cJSON.c" \
    -I components/device_config/include components/device_config/parse.c \
    tests/native/test_connectivity.c -lm -o "$native_dir/test-connectivity"
"$native_dir/test-connectivity"

python3 tools/simulate_m2.py --check
