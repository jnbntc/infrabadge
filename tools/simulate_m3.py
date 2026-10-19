#!/usr/bin/env python3
"""Render M3 reference screens through production C. Requires pinned IDF cJSON."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import simulate_ui as image

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['healthy', 'warning', 'critical', 'no-temperature', 'stale', 'missing']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--update', action='store_true')
    group.add_argument('--check', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='ib-m3-ui-') as temporary:
        folder = Path(temporary)
        exe = folder / 'render'
        sources = ['components/connectivity_core/snapshot.c', 'components/ui/model.c', 'components/ui/render.c',
                   'components/connectivity_core/errors.c', 'components/connectivity_ui/render.c',
                   'components/display_manager/display.c', 'tools/m3/render.c']
        includes = ['components/connectivity_core/include', 'components/connectivity_ui/include',
                    'components/ui/include', 'components/ui/generated', 'components/display_manager/include']
        cjson = Path(os.environ['IDF_PATH']) / 'components/json/cJSON'
        flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror']
        if os.environ.get('IB_SANITIZE') == '1':
            flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + flags + ['-I' + str(ROOT/p) for p in includes]
                       + ['-I' + str(cjson)] + [str(ROOT/p) for p in sources]
                       + [str(cjson/'cJSON.c'), '-lm', '-o', str(exe)], check=True)
        subprocess.run([str(exe), str(folder)], cwd=ROOT, check=True)
        for name in NAMES:
            pbm = (folder / (name + '.pbm')).read_bytes()
            png = image.png(pbm)
            fixture = ROOT / 'tests/fixtures/m3' / (name + '.pbm')
            reference = ROOT / 'docs/m3-ui' / (name + '.png')
            if args.check:
                assert fixture.read_bytes() == pbm and image.png_pixels(reference.read_bytes()) == image.png_pixels(png), name
            if args.update:
                fixture.parent.mkdir(parents=True, exist_ok=True)
                reference.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_bytes(pbm)
                reference.write_bytes(png)
    print('M3: six SYNTHETIC reference screens; no optical validation')


if __name__ == '__main__':
    main()
