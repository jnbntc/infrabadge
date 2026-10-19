#!/usr/bin/env python3
"""One bounded20min return-route window to observe the installed M2 autonomously.

No USB, provisioning, firmware, gateway clients or permanent configuration. This
is a NEW host-route scope, distinct from the completed120s authorization. A304
alone never proves reset/wake cause, frame cancellation, current or battery use.
"""
import argparse
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile

import try_local_route as route
from phase_a import save

SEED=route.observer.ROOT/'results/m2-utc-renew-20261018T025223Z-8o4xvbnm/result.json'
TRACE=route.observer.ROOT/'results/m2-phase-a-20261017T220757Z/gateway-events.jsonl'
SECONDS=1200


def classify(events):
    external=[e for e in events if e.get('peer_scope')=='external_unattributed']
    conditional304=any(e.get('http_status')==304 and e.get('conditional_request') is True for e in external)
    return {'external_http_observed':bool(external),'conditional_304_observed_at_gateway':conditional304,
            'reset_wake_cause_observed':False,'timer_cause_confirmed':False,
            'framebuffer_cancellation_confirmed':False,'full_m2_validation':False}


def seed_ready(now):
    return route.seed_is_recent(json.loads(SEED.read_text()),now,SECONDS+60)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--authorized-next-cycle-route',action='store_true')
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    for key in ('interface','hostname','address','network'):parser.add_argument('--'+key,help=argparse.SUPPRESS)
    args=parser.parse_args();args.seconds=SECONDS
    if args.child:
        if not args.authorized_next_cycle_route:parser.error('Explicit route-window authorization required')
        def interrupted(signum,frame):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,interrupted)
        try:route.route_capture(args)
        except KeyboardInterrupt:pass
        return 0
    if os.geteuid()==0:parser.error('Iniciar SIN sudo')
    net=json.loads((route.observer.LAB/'network.json').read_text())
    active=route.read('ip','-j','address','show','dev',net['interface'])
    prefix=next(a['prefixlen'] for dev in active for a in dev.get('addr_info',[]) if a.get('local')==net['address'])
    network=str(ipaddress.ip_network(net['address']+'/'+str(prefix),strict=False))
    route.check_scope(net['interface'],net['address'],network)
    ready=seed_ready(dt.datetime.now(dt.timezone.utc))
    if args.plan or not args.authorized_next_cycle_route:
        print('Plan: misma regla TCP8443 acotada; máximo20min; retirada exacta. Sin USB/provisión/firmware. Margen UTC: '+str(ready))
        return 0 if ready else 1
    if not sys.stdin.isatty():parser.error('Terminal interactiva normal requerida')
    if not ready:raise ValueError('UTC no deja margen; no renovar ni aplicar regla automáticamente')
    with socket.create_connection((net['address'],8443),timeout=3):pass
    if subprocess.run(['sudo','-v']).returncode:raise ValueError('sudo no disponible')
    # Recheck after waiting for a password; no board writes to extend the lease.
    if not seed_ready(dt.datetime.now(dt.timezone.utc)):raise ValueError('UTC insuficiente tras espera')
    os.umask(0o077)
    out=Path(tempfile.mkdtemp(prefix='m2-next-cycle-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=route.observer.ROOT/'results'))
    offset=TRACE.stat().st_size
    result={'status':'running','duration_limit_seconds':SECONDS,'events':[],'gateway_events':[],
            'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'flash_performed':False,
            'provision_performed':False,'serial_port_opened':False,'persistent_settings_changed':False,
            'raw_packets_saved':False,'board_identifiers_saved':False,'operator_confirmation_pending':True}
    save(out/'result.json',result)
    print('Resultados: '+str(out),flush=True)
    command=['sudo','-n',str(Path(sys.executable).resolve()),str(Path(__file__).resolve()),'--child','--authorized-next-cycle-route','--interface',net['interface'],'--hostname',net['hostname'],'--address',net['address'],'--network',network]
    process=None
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            event=json.loads(line);result['events'].append(event)
            if event.get('event')=='capture_ready':
                print('LISTO: esperar hasta20min. NO pulsar BOOT/PWR, reiniciar, desconectar USB ni abrir monitores. Mantener gateway/notebook activos; no ejecutar otros clientes con el token.',flush=True)
            elif event.get('event')=='temporary_rule_removed':
                print('Regla retirada: '+str(event.get('test_priority_absent')),flush=True)
        result['child_exit_code']=process.wait()
    except (Exception,KeyboardInterrupt):
        result['interrupted_or_error']=True
        if process is not None:
            try:
                process.send_signal(signal.SIGINT)
                rest,_=process.communicate(timeout=15)
                result['events'].extend(json.loads(line) for line in rest.splitlines() if line.strip())
            except (ProcessLookupError,PermissionError,subprocess.TimeoutExpired):pass
    finally:
        result['temporary_rule_cleanup_confirmed']=any(e.get('event')=='temporary_rule_removed' and e.get('test_priority_absent') for e in result['events'])
        try:
            with TRACE.open('rb') as stream:
                stream.seek(offset);rows=[json.loads(line) for line in stream.read(131072).splitlines()]
            keys={'sequence','host_epoch','http_status','conditional_request','peer_scope'}
            result['gateway_events']=[r for r in rows if set(r)==keys]
        except (OSError,ValueError):result['gateway_trace_read_failed']=True
        result.update(classify(result['gateway_events']))
        result['status']='observation_collected' if result.get('child_exit_code')==0 and result['temporary_rule_cleanup_confirmed'] and not result.get('gateway_trace_read_failed') else 'partial'
        save(out/'result.json',result)
        print('304 condicional observado: '+str(result['conditional_304_observed_at_gateway']),flush=True)
        print('Estado: '+result['status']+'. Resultados: '+str(out),flush=True)
        print('No valida causa de wake, consumo ni cancelación de pantalla por sí solo. No repetir provisión ni carga.',flush=True)
    return 0 if result['status']=='observation_collected' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (Exception,KeyboardInterrupt) as error:raise SystemExit('Observación detenida: '+type(error).__name__+'. No se solicita otra provisión ni carga.') from None
