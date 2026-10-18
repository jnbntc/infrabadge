#!/usr/bin/env python3
"""Prepared10min manual-wake M2 scenarios; new explicit route/lab consent required.

No USB, provision, firmware writes, credential/interval files changed or TLS
bypass. Gateway changes exist only in memory, same private CA/cert/token hashes.
The original gateway must be stopped before starting. Existing listeners are
never signaled or replaced by this script.
"""
import argparse
import copy
import datetime as dt
import ipaddress
import hashlib
import errno
import json
import os
from pathlib import Path
import queue
import select
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time

import physical_first as first
import physical_diagnostic as diagnostic
import try_local_route as route
from phase_a import ROOT,save

sys.path.insert(0,str(ROOT/'gateway'))
SECONDS=600
SEED=ROOT/'results/m2-utc-renew-20261018T025223Z-8o4xvbnm/result.json'
STAGES=(('HEALTHY',None,'HEALTHY'),('WARNING',None,'WARNING'),('CRITICAL',None,'CRITICAL'),
        ('OFFLINE',None,'OFFLINE'),('HEALTHY',None,'HEALTHY'),('HEALTHY','http','HTTP'),('HEALTHY',None,'HEALTHY'))


def apply_stage(config,index):
    state,fault,expected=STAGES[index]
    config.devices['badge-lab'].scenario=state
    config.devices['badge-lab'].fault=fault
    config.enable_faults=fault is not None
    codes=[503] if fault else [200,304] if index==len(STAGES)-1 else [200]
    return {'index':index,'scenario':state,'fault':fault,'expected_screen':expected,'expected_http':codes}


def eligible_event(event,expected_http):
    codes=[expected_http] if isinstance(expected_http,int) else expected_http
    return set(event)=={'sequence','host_epoch','http_status','conditional_request','peer_scope'} and event['peer_scope']=='external_unattributed' and event['http_status'] in codes and (event['http_status']!=304 or event['conditional_request'] is True)


def board_usb_visible():
    # Passive sysfs inventory only; never opens a device or records an identity.
    for tty in Path('/sys/class/tty').glob('ttyACM*'):
        for parent in tty.resolve().parents:
            try:identity=((parent/'idVendor').read_text().strip(),(parent/'idProduct').read_text().strip())
            except OSError:continue
            if identity==('303a','1001'):return True
            break
    return False


def port_available(address):
    try:
        with socket.socket() as channel:
            channel.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);channel.bind((address,8443))
        return True
    except OSError as error:
        if error.errno==errno.EADDRINUSE:return False
        raise first.StopTest('gateway_bind_unavailable_errno_'+str(error.errno)) from None


def hold_route(args):
    route.emit({'event':'route_ready','seconds':args.seconds})
    end=time.monotonic()+args.seconds
    while time.monotonic()<end:time.sleep(.2)
    route.emit({'event':'route_window_finished'})


def prompt(message,deadline):
    print(message,flush=True)
    ready,_,_=select.select([sys.stdin],[],[],max(0,min(90,deadline-time.monotonic())))
    if not ready:raise first.StopTest('operator_timeout')
    value=sys.stdin.readline().strip().lower()
    if not value:raise first.StopTest('operator_no_answer')
    return value in ('s','si','sí','y','yes')


def plan():
    net=json.loads((first.LAB/'network.json').read_text())
    active=route.read('ip','-j','address','show','dev',net['interface'])
    prefix=next(a['prefixlen'] for dev in active for a in dev.get('addr_info',[]) if a.get('local')==net['address'])
    network=str(ipaddress.ip_network(net['address']+'/'+str(prefix),strict=False))
    route.check_scope(net['interface'],net['address'],network)
    if not route.seed_is_recent(json.loads(SEED.read_text()),dt.datetime.now(dt.timezone.utc),SECONDS+60):
        raise first.StopTest('seed_margin_insufficient_no_auto_provision')
    diagnostic.verify_artifacts()
    if subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()!='yes':raise first.StopTest('host_utc_not_synchronized')
    from cryptography import x509
    cert=x509.load_pem_x509_certificate((first.LAB/'server.pem').read_bytes())
    now=dt.datetime.now(dt.timezone.utc)
    if not cert.not_valid_before_utc<=now<cert.not_valid_after_utc:raise first.StopTest('server_certificate_date')
    if net['hostname'] not in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName):raise first.StopTest('server_san')
    for name in ('ca.pem','server.pem','server.key','gateway.json'):
        path=first.LAB/name
        if path.is_symlink() or path.stat().st_mode&0o077:raise first.StopTest('private_file_permissions')
    if hashlib.sha256((first.LAB/'ca.pem').read_bytes()).hexdigest()!=first.CA_SHA:raise first.StopTest('approved_ca_changed')
    from infrabadge_gateway.models import GatewayConfig
    config=GatewayConfig.model_validate_json((first.LAB/'gateway.json').read_text())
    if config.enable_faults or config.devices['badge-lab'].scenario!='HEALTHY' or config.devices['badge-lab'].fault:raise first.StopTest('baseline_gateway_changed')
    value=first.read_private(first.LAB/'device.json')
    if value['interval_seconds']!=900 or value['device_id']!='badge-lab' or hashlib.sha256(value['token'].encode()).hexdigest() not in config.devices['badge-lab'].token_sha256:raise first.StopTest('private_baseline_changed')
    # No original model or private file will be mutated by scenario selection.
    return net,network,copy.deepcopy(config)


def run_session(net,network,config):
    import uvicorn
    from phase_a_server import create_lab
    # Binding proves the old gateway is stopped. Never terminate an existing listener.
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind((net['address'],8443));listener.listen(8)
    os.umask(0o077)
    out=Path(tempfile.mkdtemp(prefix='m2-scenarios-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=ROOT/'results'))
    app=create_lab(config,config.devices['phase-a-client'].token_sha256[0],'unused','unused',out,net['address'])
    server=uvicorn.Server(uvicorn.Config(app,ssl_certfile=str(first.LAB/'server.pem'),ssl_keyfile=str(first.LAB/'server.key'),lifespan='off',access_log=False,log_level='critical'))
    worker=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    process=None;events=[];pipe=queue.Queue();stop_at=time.monotonic()+SECONDS
    result={'status':'running','stages':[],'route_events':events,'duration_limit_seconds':SECONDS,'flash_performed':False,'provision_performed':False,'serial_port_opened':False,'private_files_changed':False,'gateway_changes_memory_only':True,'full_m2_validation':False,'timer_cause_confirmed':False}
    save(out/'result.json',result);print('Resultados: '+str(out),flush=True)
    try:
        apply_stage(config,0);worker.start()
        deadline=time.monotonic()+5
        while not server.started and worker.is_alive() and time.monotonic()<deadline:time.sleep(.05)
        if not server.started:raise first.StopTest('temporary_gateway_start_failed')
        context=ssl.create_default_context(cafile=str(first.LAB/'ca.pem'))
        context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
        with socket.create_connection((net['address'],8443),timeout=3) as raw:
            with context.wrap_socket(raw,server_hostname=net['hostname']):pass
        command=['sudo','-n',str(Path(sys.executable).resolve()),str(Path(__file__).resolve()),'--route-child','--authorized-scenarios','--interface',net['interface'],'--hostname',net['hostname'],'--address',net['address'],'--network',network]
        process=subprocess.Popen(command,stdout=subprocess.PIPE,text=True)
        def read_events():
            for line in process.stdout:
                try:event=json.loads(line)
                except ValueError:continue
                events.append(event);pipe.put(event)
        reader=threading.Thread(target=read_events,daemon=True);reader.start()
        while True:
            event=pipe.get(timeout=10)
            if event.get('event')=='route_ready':break
            if event.get('event')=='temporary_rule_removed':raise first.StopTest('route_not_ready')
        for index in range(len(STAGES)):
            if process.poll() is not None or time.monotonic()>stop_at-20:raise first.StopTest('route_window_finished')
            deadline=min(stop_at-20,time.monotonic()+25)
            while board_usb_visible() and time.monotonic()<deadline:time.sleep(.2)
            if board_usb_visible():raise first.StopTest('previous_usb_still_visible_no_manual_wake')
            stage=apply_stage(config,index);result['stages'].append(stage)
            trace=out/'gateway-events.jsonl';offset=trace.stat().st_size if trace.exists() else 0
            print('ETAPA '+str(index+1)+'/'+str(len(STAGES))+': '+('HTTP503' if stage['fault'] else stage['scenario'])+'. Pulsá BOOT brevemente (<1s), una vez, y soltalo. No mantenerlo ni usar PWR/monitor.',flush=True)
            deadline=min(stop_at-10,time.monotonic()+60);matched=None
            while time.monotonic()<deadline:
                if process.poll() is not None:raise first.StopTest('route_child_ended')
                if trace.exists():
                    with trace.open('rb') as stream:stream.seek(offset);rows=[json.loads(line) for line in stream.read(65536).splitlines()]
                    candidates=[r for r in rows if eligible_event(r,stage['expected_http'])]
                    if candidates:matched=candidates[0];break
                time.sleep(.2)
            stage['gateway_event']=matched
            if not matched:raise first.StopTest('expected_external_response_not_observed')
            # Gateway responding precedes panel work; wait without any USB access.
            time.sleep(12)
            message='¿La pantalla muestra '+stage['expected_screen']+' y SIM, con reloj verificado? [s/n; otra respuesta=detener]'
            if stage['fault']:message='¿La pantalla muestra OFFLINE / CONSULTA NO VALIDA: HTTP, con estado anterior histórico? [s/n]'
            stage['screen_confirmed']=prompt(message,stop_at-5)
            save(out/'result.json',result)
            if not stage['screen_confirmed']:raise first.StopTest('screen_not_confirmed')
        result['operator_no_other_token_clients']=prompt('¿No hubo otros clientes con el token, resets ni desconexiones, sólo los BOOT indicados? [s/n]',stop_at-5)
        result['status']='scenarios_functionally_confirmed' if result['operator_no_other_token_clients'] else 'diagnostic_collected'
    except (Exception,KeyboardInterrupt) as error:
        result['status']='partial';result['stop_reason']=str(error) if isinstance(error,first.StopTest) else type(error).__name__
    finally:
        if process is not None:
            try:process.send_signal(signal.SIGINT)
            except (PermissionError,ProcessLookupError):pass
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                print('Esperando retirada por el límite independiente de10min; no iniciar otra regla.',flush=True)
                process.wait(timeout=SECONDS+10)
            reader.join(2)
        result['temporary_rule_cleanup_confirmed']=any(e.get('event')=='temporary_rule_removed' and e.get('test_priority_absent') for e in events)
        config.devices['badge-lab'].scenario='HEALTHY';config.devices['badge-lab'].fault=None;config.enable_faults=False
        server.should_exit=True
        if worker.ident:worker.join(5)
        listener.close()
        result['temporary_gateway_stopped']=not worker.is_alive()
        if not result['temporary_rule_cleanup_confirmed'] or not result['temporary_gateway_stopped']:result['status']='partial'
        save(out/'result.json',result)
        print('Estado: '+result['status']+'. Resultados: '+str(out),flush=True)
        print('Regla retirada: '+str(result['temporary_rule_cleanup_confirmed'])+'. Gateway temporal detenido. No reprovisionar ni cargar firmware.',flush=True)
    return 0 if result['status']=='scenarios_functionally_confirmed' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',action='store_true');parser.add_argument('--authorized-scenarios',action='store_true')
    parser.add_argument('--route-child',action='store_true',help=argparse.SUPPRESS)
    for key in ('interface','hostname','address','network'):parser.add_argument('--'+key,help=argparse.SUPPRESS)
    args=parser.parse_args();args.seconds=SECONDS
    if args.route_child:
        if not args.authorized_scenarios:parser.error('Authorization required')
        def interrupted(signum,frame):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,interrupted)
        try:route.route_capture(args,operation=hold_route)
        except KeyboardInterrupt:pass
        return 0
    if os.geteuid()==0:parser.error('Iniciar SIN sudo')
    net,network,config=plan()
    if args.plan or not args.authorized_scenarios:
        print('Plan PASS:7 etapas; misma regla TCP8443 máximo10min; gateway temporal en memoria; sin USB/provisión/firmware/cambio de intervalo.')
        return 0
    if not sys.stdin.isatty():parser.error('Terminal interactiva normal requerida')
    # Refuse an occupied port with a clear message; never signal an unknown service.
    if not port_available(net['address']):raise first.StopTest('port8443_occupied_stop_original_gateway_with_CtrlC')
    if subprocess.run(['sudo','-v']).returncode:return 1
    net,network,config=plan()  # Recheck clock/routing after password delay.
    try:
        return run_session(net,network,config)
    finally:
        # Restore the original lab service using its unchanged saved material.
        # Never kill or replace a listener that remained active after an error.
        try:
            with socket.socket() as check:
                check.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);check.bind((net['address'],8443))
        except OSError:
            print('Puerto ocupado: no se reemplaza otro listener. Revisar el resultado antes de reiniciar el gateway.',flush=True)
        else:
            print('Reabriendo gateway original HEALTHY con sus archivos intactos. Dejá esta terminal abierta; Ctrl+C detiene sólo el gateway.',flush=True)
            from phase_a_server import serve_saved
            serve_saved(first.PHASE_A,first.LAB)


if __name__=='__main__':
    try:raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as error:raise SystemExit('Sesión detenida: '+(str(error) if isinstance(error,first.StopTest) else type(error).__name__)+'. No repetir cargas ni provisiones; conservar resultados si existen.') from None
