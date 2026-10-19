#!/usr/bin/env python3
"""Phase A host preparation. Never imports serial or invokes a hardware command."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
CI='9c5ef573254e0348b070bd0831d1222f9a57d77f'
SDK='b774170ff46c393eeb5e495ea37936038d3f4f4f'
APPROVED=ROOT/'results/m11-physical-20261017T201841Z-62tkzs1t/approved-timer-artifacts'
FIRMWARE=['components','main','config','CMakeLists.txt','sdkconfig.defaults','dependencies.lock.json']

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.chmod(0o600);temp.replace(path)

def run(command,**kwargs):
    return subprocess.run(command,check=True,cwd=ROOT,**kwargs)

def source_check():
    run(['git','diff','--quiet',CI,'--',*FIRMWARE])
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()

def partitions(path):
    data=Path(path).read_bytes();entries=[]
    for start in range(0,len(data),32):
        row=data[start:start+32]
        if row[:2]==b'\xeb\xeb':
            if row[16:32]!=hashlib.md5(data[:start]).digest():raise ValueError('partition MD5')
            return entries
        if row[:2]!=b'\xaa\x50':raise ValueError('partition entry')
        _,kind,subtype,offset,size,label,flags=struct.unpack('<HBBII16sI',row)
        entries.append({'label':label.split(b'\0')[0].decode('ascii'),'type':kind,'subtype':subtype,'offset':offset,'bytes':size,'flags':flags})
    raise ValueError('partition digest missing')

def rollback(out):
    manifest=json.loads((APPROVED/'manifest.json').read_text());verified={}
    for name,expected in manifest['artifacts'].items():
        source=APPROVED/name;data=source.read_bytes()
        if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:raise ValueError('approved rollback mismatch')
        target=out/'rollback-m11'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);target.chmod(0o400);verified[name]=expected
    save(out/'rollback-m11/manifest.json',manifest)
    save(out/'rollback-verification.json',{'status':'passed','originals_unchanged':True,'artifacts':verified,'partitions':partitions(APPROVED/'partition_table/partition-table.bin'),'hardware_io_performed':False})
    save(out/'rollback-m11/plan.json',{'requires_new_authorization':True,'executed':False,'offsets':{'0x0':'bootloader/bootloader.bin','0x8000':'partition_table/partition-table.bin','0x10000':'infrabadge.bin'},'nvs_preserved':True,'factory_backup_touched':False})

def build(out):
    source_check()
    if os.environ.get('IDF_PATH') is None:raise ValueError('IDF environment')
    if subprocess.check_output(['git','-C',os.environ['IDF_PATH'],'rev-parse','HEAD'],text=True).strip()!=SDK:raise ValueError('SDK mismatch')
    folder=out/'build';folder.mkdir()
    with (out/'build.log').open('w') as log:
        env=dict(os.environ,IB_SANITIZE='1')
        run(['bash','tools/test-m2.sh'],env=env,stdout=log,stderr=subprocess.STDOUT)
        run(['idf.py','-B',str(folder),'-DIB_BUILD_M2=ON','-DIDF_TARGET=esp32s3',f'-DSDKCONFIG={folder}/sdkconfig',f'-DSDKCONFIG_DEFAULTS={ROOT}/sdkconfig.defaults;{ROOT}/config/m2.defaults','build'],stdout=log,stderr=subprocess.STDOUT)
        run(['python3','tools/verify_build.py','--profile','connectivity','--build',str(folder),'--output',str(out/'firmware.json')],stdout=log,stderr=subprocess.STDOUT)
        run(['python3','-m','esptool','--chip','esp32s3','image_info',str(folder/'infrabadge.bin')],stdout=log,stderr=subprocess.STDOUT)
    table=partitions(folder/'partition_table/partition-table.bin')
    old=partitions(APPROVED/'partition_table/partition-table.bin')
    if table!=old:raise ValueError('partition layout changed from approved M1.1')
    app=next(p for p in table if p['type']==0);nvs=next(p for p in table if p['label']=='nvs')
    size=(folder/'infrabadge.bin').stat().st_size
    if app['offset']!=0x10000 or app['bytes']!=1048576 or app['subtype']!=0:raise ValueError('unexpected app')
    config=json.loads((folder/'config/sdkconfig.json').read_text())
    for key in ['SECURE_BOOT','SECURE_BOOT_V2_ENABLED','SECURE_FLASH_ENC_ENABLED','BOOTLOADER_APP_ANTI_ROLLBACK','NVS_ENCRYPTION','ESP_TLS_INSECURE','ESP_TLS_SKIP_SERVER_CERT_VERIFY']:
        if config.get(key):raise ValueError('unexpected security config')
    if not config.get('MBEDTLS_HAVE_TIME_DATE') or not config.get('LWIP_DNS_SUPPORT_MDNS_QUERIES'):raise ValueError('date/mDNS disabled')
    artifacts=out/'firmware-m2';artifacts.mkdir()
    for name in ['infrabadge.bin','infrabadge.elf','bootloader/bootloader.bin','partition_table/partition-table.bin','flasher_args.json']:
        target=artifacts/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(folder/name,target);target.chmod(0o400)
    save(out/'partition-review.json',{'partitions':table,'matches_approved_m11':True,'app_bytes':size,'app_capacity':app['bytes'],'app_free':app['bytes']-size,'app_free_percent':round(100*(app['bytes']-size)/app['bytes'],3),'ota_slots':0,'ota_supported_current_layout':False,'nvs_preserved_by_planned_firmware_ranges':True,'nvs':nvs,'flash_performed':False})
    source_check()

def host_network():
    routes=json.loads(subprocess.check_output(['ip','-j','route','get','1.1.1.1'],text=True))
    route=routes[0];address=route.get('prefsrc') or route.get('src')
    if not address or not ipaddress.ip_address(address).is_private or not route['dev'].startswith(('wl','en','eth')):raise ValueError('select LAN interface manually')
    synced=subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()=='yes'
    if not synced:raise ValueError('host UTC is not synchronized')
    name=socket.gethostname().split('.')[0]+'.local'
    return address,name,route['dev']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside-build',action='store_true');p.add_argument('--serve',action='store_true');p.add_argument('--serve-saved',action='store_true');p.add_argument('--result',type=Path);p.add_argument('--private',type=Path)
    a=p.parse_args()
    if os.geteuid()==0:p.error('Ejecutar SIN sudo')
    os.umask(0o077)
    if a.inside_build:
        build(a.result);return
    if a.serve_saved:
        sys.path.insert(0,str(ROOT/'gateway'));from phase_a_server import serve_saved
        serve_saved(a.result,a.private);return
    if a.serve:
        sys.path.insert(0,str(ROOT/'gateway'));from phase_a_server import serve
        serve(a.result,a.private);return
    head=source_check();stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT/'results'/('m2-phase-a-'+stamp);out.mkdir(mode=0o700)
    print('Resultados: '+str(out),flush=True)
    private=Path.home()/'.local/share/infrabadge-lab'/('phase-a-'+stamp)
    try:
        rollback(out)
        address,hostname,interface=host_network()
        save(out/'source.json',{'checkout':head,'firmware_source_ci':CI,'firmware_paths_match_ci':True,'idf_commit':SDK,'flash_performed':False})
        print('Rollback M1.1 verificado. Reconstruyendo M2 en un directorio separado; sin acceso a la placa.',flush=True)
        run(['podman','container','exists','iot-dev'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with (out/'container.log').open('w') as log:
            run(['distrobox','enter','--name','iot-dev','--','/usr/local/bin/idf-env','python3',str(Path(__file__).resolve()),'--inside-build','--result',str(out)],stdout=log,stderr=subprocess.STDOUT)
        private.mkdir(parents=True,mode=0o700)
        save(private/'network.json',{'address':address,'hostname':hostname,'interface':interface,'host_utc_synchronized':True})
        python=private/'venv/bin/python'
        with (out/'dependencies.log').open('w') as log:
            run([sys.executable,'-m','venv',str(private/'venv')],stdout=log,stderr=subprocess.STDOUT)
            run([str(python),'-m','pip','install','--require-hashes','-r','gateway/requirements.lock'],stdout=log,stderr=subprocess.STDOUT)
        save(out/'private-location.json',{'directory':str(private)})
        run([str(python),str(Path(__file__).resolve()),'--serve','--result',str(out),'--private',str(private)])
    except Exception:
        save(out/'phase-a-status.json',{'status':'blocked','flash_performed':False,'provision_performed':False,'hardware_io_performed':False})
        print('Fase A detenida. Revisar resultados privados; no se abrió ni escribió la placa.',flush=True)
        raise SystemExit(1) from None
if __name__=='__main__':main()
