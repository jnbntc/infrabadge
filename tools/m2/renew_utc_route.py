#!/usr/bin/env python3
"""One separately authorized USB reprovisioning, then the authorized route trial.

No esptool, flash, erase or reset commands. The existing protocol rewrites the
same private configuration in NVS and clears its cached snapshot; it is not a
clock-only command. Importing/--help never opens USB.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import physical_first as first
import physical_diagnostic as diagnostic
from phase_a import ROOT, SDK, save
from provision import read_private, wire
from sanitize_logs import ANSI


def previous_attempt(root=ROOT/'results'):
    for record in root.glob('m2-utc-renew-*/result.json'):
        if json.loads(record.read_text()).get('provision_attempted'):
            return record.parent
    return None


def exchange(channel, result, record, *, clock=time.monotonic, epoch=time.time):
    """Send at most once, only after an exact READY; keep raw text private."""
    deadline=clock()+40
    while clock()<deadline:
        text=ANSI.sub('',channel.readline(2048).decode('utf-8',errors='replace')).strip()
        if text=='IBPROV_READY' and not result['provision_attempted']:
            value=read_private(first.LAB/'device.json')
            stamp=int(epoch())
            result.update(provision_attempted=True,provision_utc=dt.datetime.fromtimestamp(stamp,dt.timezone.utc).isoformat())
            save(record,result)  # Persist intent before TX; never retry after uncertain writes.
            channel.write(wire(value,stamp));channel.flush()
            del value
            print('Configuración enviada una vez; soltá BOOT y dejá los botones sueltos.',flush=True)
        elif text=='IBPROV_OK':
            if not result['provision_attempted']:raise first.StopTest('ack_without_this_attempt')
            result['provision_ack']=True;save(record,result)
            return
        elif text in ('IBPROV_ERROR','IBPROV_TIMEOUT'):
            raise first.StopTest('provision_rejected_no_retry')
    raise first.StopTest('provision_window_or_ack_not_observed_no_retry')


def inside(out):
    import serial
    from serial.tools import list_ports
    record=out/'result.json';result=json.loads(record.read_text())
    if result.get('provision_attempted'):raise first.StopTest('attempt_already_consumed')
    if not 0<=time.time()-result['host_preflight_epoch']<90:raise first.StopTest('host_time_preflight_stale')
    sdk=os.environ.get('IDF_PATH')
    if not sdk or subprocess.check_output(['git','-C',sdk,'rev-parse','HEAD'],text=True).strip()!=SDK:raise first.StopTest('sdk_mismatch')
    diagnostic.verify_artifacts()
    print('LISTO USB: pulsá BOOT durante3 segundos y soltalo. No PWR/reset; no desconectar USB. Se abrirá el puerto una sola vez.',flush=True)
    deadline=time.monotonic()+30;port=None
    while time.monotonic()<deadline:
        ports=[p for p in list_ports.comports() if (p.vid,p.pid)==(0x303a,0x1001)]
        if len(ports)>1:raise first.StopTest('ambiguous_usb_board')
        if ports:port=ports[0].device;break
        time.sleep(.1)
    if port is None:raise first.StopTest('usb_not_visible_no_retry')
    channel=serial.Serial(port=None,baudrate=115200,timeout=.25,write_timeout=2,exclusive=True)
    channel.port=port;channel.dtr=False;channel.rts=False
    try:
        channel.open()
        print('Puerto abierto: si no estabas pulsando BOOT, pulsalo ahora3 segundos y soltalo. Esperando ventana; no se solicita reset.',flush=True)
        exchange(channel,result,record)
        result['status']='utc_provision_acknowledged'
    except (Exception,KeyboardInterrupt) as error:
        result['status']='partial';result['stop_reason']=str(error) if isinstance(error,first.StopTest) else type(error).__name__
    finally:
        channel.close();save(record,result)
    return 0 if result['status']=='utc_provision_acknowledged' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-reprovision-and-route',action='store_true')
    parser.add_argument('--inside',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if os.geteuid()==0 or not args.authorized_reprovision_and_route or not sys.stdin.isatty():parser.error('Terminal normal, SIN sudo y autorización nueva para UNA provisión requeridos')
    if args.inside:return inside(args.inside)
    with (Path(tempfile.gettempdir())/('infrabadge-physical-'+str(os.getuid())+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if previous_attempt():raise first.StopTest('USB_renewal_already_attempted_review_results_before_another_write')
        subprocess.run([sys.executable,str(ROOT/'tools/m2/try_local_route.py'),'--plan'],check=True)
        first.host_preflight(artifact_verifier=diagnostic.verify_artifacts)
        os.umask(0o077)
        out=Path(tempfile.mkdtemp(prefix='m2-utc-renew-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=ROOT/'results'))
        save(out/'result.json',{'status':'prepared','host_preflight_epoch':time.time(),'app_sha256':diagnostic.APP_SHA,'flash_performed':False,'provision_attempted':False,'provision_ack':False,'raw_serial_text_stored':False,'board_identifiers_saved':False})
        print('Resultados: '+str(out),flush=True)
        command=['distrobox','enter','--name','iot-dev','--','/usr/local/bin/idf-env','python3',str(Path(__file__).resolve()),'--authorized-reprovision-and-route','--inside',str(out)]
        if subprocess.run(command).returncode:return 1
        print('Provisión confirmada. Puerto cerrado; comienza la prueba temporal de ruta ya autorizada.',flush=True)
        return subprocess.run([sys.executable,str(ROOT/'tools/m2/try_local_route.py'),'--authorized-temporary-route','--seed-record',str(out/'result.json')]).returncode


if __name__=='__main__':
    try:raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as error:raise SystemExit('Preparación detenida: '+(str(error) if isinstance(error,first.StopTest) else type(error).__name__)+'. Sin recarga ni reintento automático.') from None
