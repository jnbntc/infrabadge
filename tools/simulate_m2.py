#!/usr/bin/env python3
"""Synthetic M2 screens rendered by firmware C, no physical network evidence."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import simulate_ui as image
ROOT=Path(__file__).resolve().parents[1]
NAMES=['healthy','warning','critical','unknown','network-error','clock-error']
def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--update',action='store_true')
    group.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'results/m2-preview')
    args=parser.parse_args()
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='infrabadge-m2-ui-') as folder:
        folder=Path(folder);exe=folder/'m2-sim'
        subprocess.run(shlex.split(os.environ.get('CC','cc'))+['-std=c11','-O1','-g','-Wall','-Wextra','-Werror']+(['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if os.environ.get('IB_SANITIZE')=='1' else [])+[
            '-I'+str(ROOT/'components/connectivity_core/include'),'-I'+str(ROOT/'components/connectivity_ui/include'),
            '-I'+str(ROOT/'components/ui/include'),'-I'+str(ROOT/'components/ui/generated'),
            '-I'+str(ROOT/'components/display_manager/include'),
            str(ROOT/'components/connectivity_core/errors.c'),str(ROOT/'components/ui/model.c'),str(ROOT/'components/ui/render.c'),
            str(ROOT/'components/display_manager/display.c'),str(ROOT/'components/connectivity_ui/render.c'),
            str(ROOT/'tools/m2_sim.c'),'-o',str(exe)],check=True)
        subprocess.run([str(exe),str(folder)],check=True)
        for name in NAMES:
            stem='simulated-'+name
            pbm=(folder/(stem+'.pbm')).read_bytes();png=image.png(pbm)
            fixture=ROOT/'tests/fixtures/connectivity'/(stem+'.pbm')
            reference=ROOT/'docs/connectivity-ui'/(stem+'.png')
            if args.check and (fixture.read_bytes()!=pbm or image.png_pixels(reference.read_bytes())!=image.png_pixels(png)):
                raise SystemExit('M2 visual reference differs: '+name)
            if args.update:
                fixture.parent.mkdir(parents=True,exist_ok=True);reference.parent.mkdir(parents=True,exist_ok=True)
                fixture.write_bytes(pbm);reference.write_bytes(png)
            (output/(stem+'.pbm')).write_bytes(pbm);(output/(stem+'.png')).write_bytes(png)
    print('M2 UI: six SYNTHETIC screens; no hardware validation; '+('references verified' if args.check else str(output)))
if __name__=='__main__':main()
