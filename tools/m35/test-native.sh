#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
: "${IDF_PATH:?Pinned SDK required}"
test "$(git -C "$IDF_PATH" rev-parse HEAD)" = b774170ff46c393eeb5e495ea37936038d3f4f4f
mkdir -p results/m35-native
flags=(-std=c11 -O1 -g -UNDEBUG -Wall -Wextra -Werror)
if [[ ${IB_SANITIZE:-0} == 1 ]]; then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer); fi
target=results/m35-native/render
if [[ ${IB_SANITIZE:-0} == 1 ]]; then target+=-sanitized; fi
cc "${flags[@]}" -I components/m35_ui/include -I components/connectivity_core/include \
    -I components/ui/include -I components/display_manager/include -I components/render/include \
    -I components/render/generated -I components/ui/generated -I "$IDF_PATH/components/json/cJSON" \
    components/m35_ui/{decode,state,render}.c components/connectivity_core/snapshot.c \
    components/display_manager/display.c components/ui/render.c components/ui/model.c "$IDF_PATH/components/json/cJSON/cJSON.c" tools/m35/native.c -lm -o "$target"
if [[ ${1:-} == --build-only ]]; then exit 0; fi
IB_M35_NATIVE="$PWD/$target" python3 tools/m35/firmware_visuals.py --check
