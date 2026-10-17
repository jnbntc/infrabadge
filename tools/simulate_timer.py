#!/usr/bin/env python3
"""Synthetic timer state/screens, never evidence of physical PASS."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import simulate_ui as image
ROOT=Path(__file__).resolve().parents[1]
NAMES=['ready-0','run-0','run-1','run-2','pass-3','invalid-3']
def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--update',action='store_true')
    group.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'results/m11-preview')
    args=parser.parse_args()
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='infrabadge-timer-') as folder:
        folder=Path(folder);exe=folder/'timer-sim'
        subprocess.run(shlex.split(os.environ.get('CC','cc'))+['-std=c11','-O2','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'components/timer_diag/include'),'-I'+str(ROOT/'components/ui/generated'),
            str(ROOT/'components/timer_diag/state.c'),str(ROOT/'components/timer_diag/render.c'),str(ROOT/'tools/timer_sim.c'),'-o',str(exe)],check=True)
        subprocess.run([str(exe),str(folder)],check=True)
        for name in NAMES:
            stem='simulated-'+name
            pbm=(folder/(stem+'.pbm')).read_bytes();png=image.png(pbm)
            fixture=ROOT/'tests/fixtures/timer'/(stem+'.pbm')
            reference=ROOT/'docs/power-ui'/(stem+'.png')
            if args.check and (fixture.read_bytes()!=pbm or image.png_pixels(reference.read_bytes())!=image.png_pixels(png)):
                raise SystemExit('Timer visual reference differs: '+name)
            if args.update:
                fixture.parent.mkdir(parents=True,exist_ok=True);reference.parent.mkdir(parents=True,exist_ok=True)
                fixture.write_bytes(pbm);reference.write_bytes(png)
            (output/(stem+'.pbm')).write_bytes(pbm);(output/(stem+'.png')).write_bytes(png)
    print('Timer UI: six SYNTHETIC screens; no physical PASS; '+('references verified' if args.check else str(output)))
if __name__=='__main__':main()
