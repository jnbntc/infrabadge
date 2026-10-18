#!/usr/bin/env python3
"""Prepare a reviewable M2 diagnostic lab or execute ONE approved manifest.

Default/help/prepare never touch the board. No scheduled execution, automatic
flash retry, whole-flash erase, eFuse write or TLS bypass. Measurement deferred.
"""
import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import queue
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

from phase_a import ROOT,save
from provision import read_private
import physical_first as first
import try_local_route as route
from auto_lab import CASES,Lab,certificates
from auto_scope import authorization

sys.path.insert(0,str(ROOT/'gateway'))
sys.path.insert(0,str(ROOT/'tools'))
SECONDS=3000


def range_rule(action,address,network):
    command=route.rule_command(action,address,network)
    command[command.index('sport')+1]='8443-8474'
    return command


def root_window(a):
    if os.geteuid()!=0:raise ValueError('root_child_required')
    route.check_scope(a.interface,a.address,a.network);attempted=False
    try:
        attempted=True
        subprocess.run(range_rule('add',a.address,a.network),check=True,capture_output=True,timeout=5)
        if route.reply_route(a.address,a.network)!=a.interface:raise ValueError('return_route_not_wifi')
        route.emit({'event':'route_ready','seconds':SECONDS});end=time.monotonic()+SECONDS
        while time.monotonic()<end:time.sleep(.2)
    finally:
        if attempted:
            signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN)
            code=subprocess.run(range_rule('del',a.address,a.network),capture_output=True,timeout=5).returncode
            absent=not any(r.get('priority')==route.PRIORITY for r in route.read('ip','-j','rule','show'))
            route.emit({'event':'route_removed','delete_completed':code==0,'priority_absent':absent})
            if not absent:raise ValueError('route_cleanup_not_confirmed')


def check_pack(pack):
    import verify_build
    actual=verify_build.inspect(pack,'automation');declared=json.loads((pack/'manifest.json').read_text())
    if actual['artifacts']!=declared['artifacts']:raise ValueError('pack_manifest_mismatch')
    for name,digest in declared['firmware_inputs'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('sources_changed_since_build')
    rollback=first.PHASE_A/'rollback-m11/partition_table/partition-table.bin'
    if (pack/'partition_table/partition-table.bin').read_bytes()!=rollback.read_bytes():raise ValueError('partition_layout_changed')
    match=re.search(r'SHA-256:\s*`([0-9a-f]{64})`',first.FACTORY_RECORD.read_text())
    if not match or first.FACTORY.stat().st_size!=8388608:raise ValueError('factory_backup_unavailable')
    with first.FACTORY.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=match[1]:raise ValueError('factory_backup_hash')
    app=actual['artifacts']['infrabadge.bin']
    if app['bytes']>0x100000:raise ValueError('application_partition_overflow')
    return actual


def prepare(pack,private,previous=None):
    pack=pack.resolve(strict=True);private=private.expanduser().resolve()
    if private.exists() or private.is_relative_to(ROOT.resolve()):raise ValueError('new_private_folder_outside_git_required')
    checked=check_pack(pack)
    if subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()!='yes':raise ValueError('host_utc_not_synchronized')
    source=read_private(first.LAB/'device.json');net=json.loads((first.LAB/'network.json').read_text())
    if source['interval_seconds']!=900:raise ValueError('normal_configuration_changed')
    os.umask(0o077);private.mkdir(mode=0o700,parents=True)
    run=secrets.token_hex(16);fingerprint=certificates(private,net['hostname'],run)
    device=dict(source,device_id='auto-'+run[:8],token=secrets.token_urlsafe(32),ca_pem=(private/'ca.pem').read_text(),interval_seconds=60)
    device['wifi_timeout_ms']=15000;device['http_timeout_ms']=5000
    save(private/'device.json',device);save(private/'network.json',net)
    target=private/'firmware';shutil.copytree(pack,target)
    manifest={'version':1,'run':run,'application':dict(checked['artifacts']['infrabadge.bin'],offset=65536),
      'authorization':{'app_writes':1,'setups':1,'exports':1,'restore_firmware':False},'route_seconds':SECONDS,
      'tcp_ports':[8443,8474],'cases':len(CASES),'ca_sha256':fingerprint,'normal_lab':str(first.LAB),
      'measurements':'deferred_by_user','requires_initial_unique_waveshare_and_possible_boot_wake':True,
      'leaves_diagnostic_installed':True,'no_erase_all_efuse_or_security_changes':True}
    if previous is not None:
        manifest['execution_mode']='setup_existing'
        manifest['authorization']=authorization('setup_existing')
        save(private/'previous-report.json',previous)
        manifest['previous_journal_sha256']=hashlib.sha256((private/'previous-report.json').read_bytes()).hexdigest()
    manifest['sealed_inputs']={name:hashlib.sha256((private/name).read_bytes()).hexdigest() for name in ('device.json','network.json','ca.pem','good.pem','good.key','foreign_ca.pem','foreign_ca.key','wrong_san.pem','wrong_san.key','expired_cert.pem','expired_cert.key')}
    save(private/'manifest.json',manifest)
    print('Manifiesto preparado: '+str(private/'manifest.json'),flush=True)
    print('App SHA256 '+manifest['application']['sha256']+'; bytes '+str(manifest['application']['bytes'])+'; offset0x10000.',flush=True)
    print('Propuesta:26 casos/25 timer,'+('0 cargas/1 reset USB' if previous is not None else '1 carga')+'/1 setup/1 export,regla50min TCP8443-8474. Deja diagnóstico instalado; no se ejecutó hardware.',flush=True)


def prepare_restart(previous_private,private):
    """Preserve terminal evidence before proposing a setup-only new run."""
    from auto_report import validate
    prior=validate_manifest(previous_private)
    result_dir=Path(json.loads((previous_private/'execution.json').read_text())['results']).resolve()
    if not result_dir.is_relative_to((ROOT/'results').resolve()):raise ValueError('previous_result_location')
    result=json.loads((result_dir/'result.json').read_text());loaded=json.loads((result_dir/'load-setup.json').read_text())
    collected=json.loads((result_dir/'collect.json').read_text());report=json.loads((result_dir/'device-report.json').read_text())
    validate(report,prior['run'])
    if not (loaded.get('flash_completed') and loaded.get('setup_ack') and collected.get('status')=='completed' and report['phase'] in (3,4)):
        raise ValueError('previous_terminal_journal_required')
    if not (result.get('route_cleanup_confirmed') and result.get('test_gateway_stopped')):raise ValueError('previous_cleanup_not_confirmed')
    prepare(previous_private/'firmware',private,report)


def validate_manifest(private):
    path=private/'manifest.json'
    if private.stat().st_mode&0o077 or path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('private_manifest_permissions')
    value=json.loads(path.read_text())
    if value.get('version')!=1 or value.get('cases')!=26 or value.get('route_seconds')!=SECONDS or value.get('tcp_ports')!=[8443,8474]:raise ValueError('unsupported_manifest')
    if not re.fullmatch('[0-9a-f]{32}',value.get('run','')):raise ValueError('manifest_run')
    mode=value.get('execution_mode','load_setup')
    if value.get('authorization')!=authorization(mode):raise ValueError('authorization_scope')
    if mode=='setup_existing':
        from auto_report import validate
        previous=private/'previous-report.json'
        if hashlib.sha256(previous.read_bytes()).hexdigest()!=value.get('previous_journal_sha256'):raise ValueError('previous_journal_changed')
        report=json.loads(previous.read_text());validate(report,report['run'])
        if report['phase'] not in (3,4) or report['run']==value['run']:raise ValueError('previous_journal_not_terminal')
    for name,digest in value.get('sealed_inputs',{}).items():
        file=(private/name).resolve()
        if not file.is_relative_to(private.resolve()) or hashlib.sha256(file.read_bytes()).hexdigest()!=digest:raise ValueError('sealed_lab_input_changed')
    required={'device.json','network.json','ca.pem','good.pem','good.key','foreign_ca.pem','foreign_ca.key','wrong_san.pem','wrong_san.key','expired_cert.pem','expired_cert.key'}
    if set(value.get('sealed_inputs',{}))!=required:raise ValueError('missing_sealed_lab_inputs')
    actual=check_pack(private/'firmware')
    if value['application']!=dict(actual['artifacts']['infrabadge.bin'],offset=65536):raise ValueError('approved_image_changed')
    if hashlib.sha256((private/'ca.pem').read_bytes()).hexdigest()!=value['ca_sha256']:raise ValueError('test_ca_changed')
    return value


def execute(private):
    if os.geteuid()==0 or not sys.stdin.isatty():raise ValueError('normal_interactive_terminal_required')
    manifest=validate_manifest(private)
    if (private/'execution.json').exists():raise ValueError('manifest_already_attempted_no_retry')
    # Codex can prepare in a protected /tmp folder. The normal host invocation
    # places that identical sealed bundle in shared home before entering iot-dev.
    # Never rely on the container sharing the host's /tmp mount.
    if private.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        destination=first.LAB.parent/('m2-auto-'+manifest['run'])
        if not destination.exists():
            os.umask(0o077);shutil.copytree(private,destination)
        if validate_manifest(destination)!=manifest:raise ValueError('staged_manifest_mismatch')
        private=destination
    if (private/'execution.json').exists():raise ValueError('manifest_already_attempted_no_retry')
    device=read_private(private/'device.json');net=json.loads((private/'network.json').read_text())
    active=route.read('ip','-j','address','show','dev',net['interface'])
    prefix=next(a['prefixlen'] for d in active for a in d.get('addr_info',[]) if a.get('local')==net['address'])
    network=str(ipaddress.ip_network(net['address']+'/'+str(prefix),strict=False));route.check_scope(net['interface'],net['address'],network)
    if subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()!='yes':raise ValueError('host_utc_not_synchronized')
    # Refuse all occupied test listeners before applying a route or board action.
    probes=[]
    try:
        for port in range(8443,8475):
            sock=socket.socket();sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind((net['address'],port));probes.append(sock)
    finally:
        for sock in probes:sock.close()
    if subprocess.run(['sudo','-v']).returncode:raise ValueError('sudo_not_available')
    os.umask(0o077);out=Path(tempfile.mkdtemp(prefix='m2-auto-physical-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=ROOT/'results'))
    save(private/'execution.json',{'results':str(out),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
    save(out/'host-preflight.json',{'utc_checked_epoch':time.time()})
    result={'status':'running','events':[],'flash_and_setup_requested':False,'route_cleanup_confirmed':False,'full_m2_validation':False,'measurement_status':'deferred_by_user'}
    save(out/'result.json',result);print('Resultados: '+str(out),flush=True)
    process=None;lab=Lab(private,net,device);reader=None
    try:
        lab.start()
        command=['sudo','-n',str(Path(sys.executable).resolve()),str(Path(__file__).resolve()),'--root-window','--interface',net['interface'],'--address',net['address'],'--network',network]
        process=subprocess.Popen(command,stdout=subprocess.PIPE,text=True);mail=queue.Queue()
        def consume():
            for line in process.stdout:
                event=json.loads(line);result['events'].append(event);mail.put(event)
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        if mail.get(timeout=10).get('event')!='route_ready':raise ValueError('route_not_ready')
        def sdk(action):
            command=['distrobox','enter','--name','iot-dev','--','/usr/local/bin/idf-env','python3',str(ROOT/'tools/m2/auto_sdk.py'),'--approved-manifest',str(private/'manifest.json'),'--action',action,'--out',str(out)]
            return subprocess.run(command,timeout=240).returncode
        action='setup-existing' if manifest.get('execution_mode')=='setup_existing' else 'load-setup'
        result['flash_and_setup_requested']=action=='load-setup';result['setup_requested']=True
        result['firmware_write_requested']=action=='load-setup';save(out/'result.json',result)
        if sdk(action):raise ValueError('load_or_setup_incomplete_no_retry')
        print('Ensayo autónomo iniciado. No BOOT/PWR, resets, monitores ni otros clientes con el token. Esperando journal terminal.',flush=True)
        end=time.monotonic()+SECONDS-240
        while time.monotonic()<end and process.poll() is None and not lab.terminal_seen():time.sleep(1)
        if not lab.terminal_seen():raise ValueError('terminal_notice_missing_no_timer_pass_inferred')
        if sdk('collect'):raise ValueError('journal_export_incomplete')
        result.update(json.loads((out/'device-summary.json').read_text()))
    except (Exception,KeyboardInterrupt) as error:
        result['status']='incomplete_or_failed';result['stop_reason']=type(error).__name__
    finally:
        save(out/'gateway-events.json',lab.events)
        result['test_gateway_stopped']=lab.stop()
        if process:
            try:process.send_signal(signal.SIGINT)
            except (ProcessLookupError,PermissionError):pass
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:process.wait(timeout=SECONDS+10)
            if reader:reader.join(2)
        result['route_cleanup_confirmed']=any(e.get('event')=='route_removed' and e.get('priority_absent') for e in result['events'])
        if not result['route_cleanup_confirmed'] or not result['test_gateway_stopped']:result['status']='incomplete_or_failed'
        save(out/'result.json',result)
        print('Estado: '+result['status']+'. Resultados: '+str(out),flush=True)
        print('No se restaura firmware automáticamente. Diagnóstico queda instalado; mediciones pendientes.',flush=True)
        # Restore only the original lab service, never credentials or board flash.
        if result['test_gateway_stopped']:
            from phase_a_server import serve_saved
            print('Reabriendo gateway original con sus archivos intactos.',flush=True)
            serve_saved(first.PHASE_A,first.LAB)
    return 0 if result['status']=='diagnostic_cases_confirmed' else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',type=Path,help='Frozen approved-auto-artifacts pack');p.add_argument('--prepare-restart',type=Path,help='Previous private lab with preserved terminal journal; prepares only');p.add_argument('--private',type=Path);p.add_argument('--execute-approved-manifest',action='store_true');p.add_argument('--root-window',action='store_true',help=argparse.SUPPRESS)
    for key in ('interface','address','network'):p.add_argument('--'+key,help=argparse.SUPPRESS)
    a=p.parse_args()
    if a.root_window:
        def interrupted(signum,frame):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,interrupted)
        try:root_window(a)
        except KeyboardInterrupt:pass
        return 0
    if not a.private or sum(bool(x) for x in (a.prepare,a.prepare_restart,a.execute_approved_manifest))!=1:p.error('Elegir --prepare PACK, --prepare-restart ANTERIOR o --execute-approved-manifest, con --private CARPETA')
    if a.prepare:prepare(a.prepare,a.private);return 0
    if a.prepare_restart:prepare_restart(a.prepare_restart.resolve(strict=True),a.private);return 0
    return execute(a.private.resolve(strict=True))


def stop_message(error):
    # Explain the safety latch without echoing arbitrary exception text, which
    # can contain private filenames or configuration values.
    if isinstance(error,ValueError) and error.args==('manifest_already_attempted_no_retry',):
        return ('Ejecución bloqueada: este manifiesto ya fue intentado. No se inició '
                'otra carga, provisión ni ruta. Conservar execution.json y revisar '
                'los resultados; una repetición requiere un plan nuevo.')
    return 'Automatización detenida: '+type(error).__name__+'. No reintentar escrituras; revisar manifiesto/resultados.'


if __name__=='__main__':
    try:raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as error:raise SystemExit(stop_message(error)) from None
