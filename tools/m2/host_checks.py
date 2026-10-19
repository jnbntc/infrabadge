#!/usr/bin/env python3
"""One software-validation command. Never flashes, provisions or opens board USB.

Use the existing locked gateway venv. --build also invokes the six-profile SDK
build through its existing launcher; it requires a normal host terminal/SDK.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true',help='Also run six firmware builds, native sanitizer and visual checks; no hardware')
    args=parser.parse_args()
    if os.geteuid()==0:parser.error('Ejecutar SIN sudo en la venv existente del gateway')
    os.umask(0o077)
    out=Path(tempfile.mkdtemp(prefix='m2-host-checks-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=ROOT/'results'))
    result={'status':'running','steps':[],'firmware_build_requested':args.build,'firmware_build_passed':False,
            'flash_performed':False,'provision_performed':False,'board_usb_opened':False,'hardware_validation':False}
    print('Resultados: '+str(out),flush=True)
    try:
        result['git_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        result['working_tree_has_changes']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
        commands=[('protocol',[sys.executable,'tools/m2/generate_protocol.py','--check'],60),
                  ('python',[sys.executable,'-m','pytest','-q','gateway/tests'],120)]
        if args.build:commands.append(('six_profile_sdk_build',['bash','tools/build-m2.sh','--all'],1800))
        for name,command,limit in commands:
            step={'name':name,'exit_code':None};result['steps'].append(step)
            with (out/(name+'.log')).open('x') as log:
                try:step['exit_code']=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=limit).returncode
                except subprocess.TimeoutExpired:step['exit_code']=124
            print(name+': '+('PASS' if step['exit_code']==0 else 'FAIL'),flush=True)
            if step['exit_code']!=0:raise RuntimeError('validation_step_failed')
        result['firmware_build_passed']=args.build
        result['status']='software_checks_passed'
    except (Exception,KeyboardInterrupt) as error:
        result['status']='incomplete_or_failed';result['stop_reason']=type(error).__name__
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('Estado: '+result['status']+'. Resultados: '+str(out),flush=True)
        print('No es validación física. No se carga firmware ni se abre USB.',flush=True)
    return 0 if result['status']=='software_checks_passed' else 1


if __name__=='__main__':raise SystemExit(main())
