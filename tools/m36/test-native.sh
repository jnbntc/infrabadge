#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
: "${IDF_PATH:?Pinned SDK required}"
test "$(git -C "$IDF_PATH" rev-parse HEAD)" = b774170ff46c393eeb5e495ea37936038d3f4f4f
mkdir -p results/m36-native
flags=(-std=c11 -O1 -g -UNDEBUG -Wall -Wextra -Werror)
if [[ ${IB_SANITIZE:-0} == 1 ]]; then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer); fi
target=results/m36-native/policy
if [[ ${IB_SANITIZE:-0} == 1 ]]; then target+=-sanitized; fi
cc "${flags[@]}" -I components/mobile_policy/include -I components/device_config/include \
    -I components/m35_ui/include -I components/connectivity_core/include -I components/ib_core/include \
    -I components/ui/include -I components/display_manager/include -I components/render/include \
    -I components/render/generated -I components/ui/generated -I tests/native/store_stubs \
    -I "$IDF_PATH/components/json/cJSON" \
    components/mobile_policy/{config,policy,store}.c components/device_config/parse.c \
    components/m35_ui/{decode,state}.c components/connectivity_core/snapshot.c \
    components/ui/{render,model}.c "$IDF_PATH/components/json/cJSON/cJSON.c" tools/m36/native.c -lm -o "$target"
python3 tools/m36/fixtures.py > results/m36-native/bundle.json
"$target" results/m36-native/bundle.json tests/fixtures/m35-wire/healthy.json results/m36-native/night.pbm
if [[ ${1:-} != --build-only ]]; then
    IB_M36_NATIVE="$PWD/$target" python3 tools/m36/visual.py --check
fi
cc "${flags[@]}" -I tests/native/mobile_stubs -I components/mobile_policy/include \
    -I components/device_config/include -I components/m35_ui/include -I components/connectivity_core/include \
    -I components/ib_core/include -I components/ui/include -I components/display_manager/include \
    -I components/render/include -I components/render/generated -I components/ui/generated \
    -I components/hal_waveshare_v2/include -I components/power_manager/include -I components/epaper/include \
    -I components/wifi_manager/include -I components/https_client/include -I "$IDF_PATH/components/json/cJSON" \
    components/mobile_policy/{config,policy}.c components/device_config/parse.c \
    components/m35_ui/{decode,state,render}.c components/display_manager/display.c \
    components/connectivity_core/{snapshot,errors}.c components/ui/{render,model}.c \
    "$IDF_PATH/components/json/cJSON/cJSON.c" tests/native/test_mobile_app.c -lm -o results/m36-native/app-test
results/m36-native/app-test results/m36-native/bundle.json
