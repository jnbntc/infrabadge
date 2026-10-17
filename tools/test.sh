#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$project_root"
python3 tools/generate_screen.py --check
python3 -m unittest discover -s tests -v
native_dir=$(mktemp -d "${TMPDIR:-/tmp}/infrabadge-native-XXXXXX")
trap 'rm -rf -- "$native_dir"' EXIT
flags=(-std=c11 -O1 -g -UNDEBUG -Wall -Wextra -Werror)
if [[ ${IB_SANITIZE:-0} == 1 ]]; then
    flags+=('-fsanitize=address,undefined' -fno-omit-frame-pointer)
fi
"${CC:-cc}" "${flags[@]}" -I components/ib_core/include -I components/render/include \
    -I components/render/generated components/ib_core/ib_data.c components/render/render.c \
    tests/native/test_core.c -o "$native_dir/test-core"
"$native_dir/test-core" tests/fixtures/m0.pbm
"${CC:-cc}" "${flags[@]}" -I tests/native/stubs -I components/epaper/include \
    -I components/hal_waveshare_v2/include -I components/ib_core/include \
    components/epaper/epaper.c tests/native/test_epaper.c -o "$native_dir/test-epaper"
"$native_dir/test-epaper"
