#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
work=$(mktemp -d "${TMPDIR:-/tmp}/ib-m2-auto-XXXXXX")
trap 'rm -rf -- "$work"' EXIT
flags=(-std=c11 -O1 -g -UNDEBUG -Wall -Wextra -Werror)
if [[ ${IB_SANITIZE:-0} == 1 ]]; then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer); fi
"${CC:-cc}" "${flags[@]}" -I components/m2_auto_diag/include -I components/connectivity_core/include \
  -I components/ui/include -I components/display_manager/include components/m2_auto_diag/state.c \
  tests/native/test_m2_auto.c -o "$work/test-auto"
"$work/test-auto"
