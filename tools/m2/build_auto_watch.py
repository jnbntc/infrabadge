#!/usr/bin/env python3
"""Finite seven-profile build supervisor; never accesses USB or flashes."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[2]


def inputs():
    paths=[]
    for folder in ('components','main','config','tests/native'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend(ROOT/name for name in ('CMakeLists.txt','sdkconfig.defaults','tools/build-m2-auto.sh','tools/test-m2-auto.sh','tools/test-m2.sh','tools/verify_build.py'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    if os.geteuid()==0:raise SystemExit('Ejecutar SIN sudo')
    if '--inside' not in sys.argv:
        os.execvp('distrobox',['distrobox','enter','--name','iot-dev','--','/usr/local/bin/idf-env','python3',str(Path(__file__).resolve()),'--inside'])
    if subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip()!='https://github.com/jnbntc/infrabadge.git':raise SystemExit('Wrong repository')
    os.umask(0o077)
    out=Path(tempfile.mkdtemp(prefix='m2-auto-supervised-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=ROOT/'results'))
    print('Resultados: '+str(out),flush=True)
    previous=None;attempt=0;end=time.monotonic()+2700
    while time.monotonic()<end:
        before=inputs()
        if before==previous:time.sleep(2);continue
        previous=before;attempt+=1
        try:
            with (out/f'attempt-{attempt}.log').open('w') as stream:
                code=subprocess.run(['bash','tools/build-m2-auto.sh','--all'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=1800).returncode
        except subprocess.TimeoutExpired:code=124
        after=inputs();status='passed' if code==0 and before==after else 'waiting_for_fix'
        result={'status':status,'attempt':attempt,'exit_code':code,'firmware_inputs':after,'hardware_io_performed':False,'flash_performed':False}
        if status=='passed':
            sys.path.insert(0,str(ROOT/'tools'));import verify_build
            build=ROOT/'build-m2-auto/diagnostic';checked=verify_build.inspect(build,'automation')
            pack=out/'approved-auto-artifacts';pack.mkdir()
            for name in list(checked['artifacts'])+['config/sdkconfig.json','project_description.json','flasher_args.json']:
                target=pack/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(build/name,target);target.chmod(0o400)
            (pack/'manifest.json').write_text(json.dumps(dict(checked,firmware_inputs=after),indent=2)+'\n');(pack/'manifest.json').chmod(0o400)
            result['artifact_pack']=str(pack)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('Intento '+str(attempt)+' '+status,flush=True)
        if status=='passed':print('Siete perfiles compilados; artefactos identificados. Sin USB, provisión ni carga.',flush=True);return
        print('Esperando correcciones de fuentes; no repetir el comando.',flush=True)
    raise SystemExit('Límite45min; revisar resultados. Sin acceso a placa.')


if __name__=='__main__':main()
