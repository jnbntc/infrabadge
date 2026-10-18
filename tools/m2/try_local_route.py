#!/usr/bin/env python3
"""Prepared, explicitly authorized, temporary gateway reply routing test.

Default/--plan are read-only. The privileged child owns the exact temporary rule
and removes it in finally after the bounded capture, including capture failures.
No USB, firmware, provisioning, persistent networking or Tailscale settings.
"""
import argparse
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
import tempfile

import observe_network as observer

PRIORITY=5100
DIAGNOSTIC=observer.ROOT/'results/m2-physical-diagnostic-20261018T014635Z-y7ofz23s/result.json'


def seed_is_recent(value,now,seconds):
    if not value.get('provision_ack') or not value.get('provision_utc'):return False
    seed=dt.datetime.fromisoformat(value['provision_utc'])
    age=(now-seed).total_seconds()
    return 0<=age<3600-seconds


def read(*command):
    return json.loads(subprocess.check_output(command,text=True,stderr=subprocess.DEVNULL,timeout=5))


def rule_command(action,address,network):
    address=str(ipaddress.IPv4Address(address));network=str(ipaddress.IPv4Network(network))
    if action not in ('add','del') or ipaddress.ip_address(address) not in ipaddress.ip_network(network):raise ValueError('Rule scope')
    return ['ip','rule',action,'priority',str(PRIORITY),'from',address+'/32','to',network,
            'ipproto','tcp','sport','8443','lookup','main']


def reply_route(address,network):
    peer=str(ipaddress.ip_network(network).network_address+2)
    if peer==address:peer=str(ipaddress.ip_network(network).network_address+3)
    return read('ip','-j','route','get',peer,'from',address,'ipproto','tcp','sport','8443','dport','50000')[0].get('dev')


def check_scope(interface,address,network):
    rule_command('add',address,network)
    if any(r.get('priority')==PRIORITY for r in read('ip','-j','rule','show')):raise ValueError('Test priority already occupied')
    active=read('ip','-j','address','show','dev',interface)
    if not any(a.get('local')==address and str(ipaddress.ip_network(address+'/'+str(a['prefixlen']),strict=False))==network for dev in active for a in dev.get('addr_info',[])):
        raise ValueError('Active Wi-Fi changed')
    main=read('ip','-j','route','show','table','main')
    if not any(r.get('dst')==network and r.get('dev')==interface and not r.get('gateway') for r in main):raise ValueError('No connected Wi-Fi route in main')
    if reply_route(address,network)!='tailscale0':raise ValueError('Original routing conflict no longer matches; re-inspect')


def emit(value):print(json.dumps(value,separators=(',',':')),flush=True)


def route_capture(args,operation=None):
    if os.geteuid()!=0:raise ValueError('Privileged child required')
    check_scope(args.interface,args.address,args.network)
    attempted=False
    try:
        attempted=True
        added=subprocess.run(rule_command('add',args.address,args.network),capture_output=True,timeout=5)
        if added.returncode:raise ValueError('Temporary rule not installed')
        if reply_route(args.address,args.network)!=args.interface:raise ValueError('Reply still does not use Wi-Fi')
        emit({'event':'temporary_rule_applied','priority':PRIORITY,'gateway_tcp_reply_uses_wifi':True})
        (operation or observer.capture)(args)
    finally:
        if attempted:
            # Let cleanup finish if the user interrupts the trial again.
            signal.signal(signal.SIGINT,signal.SIG_IGN)
            signal.signal(signal.SIGTERM,signal.SIG_IGN)
            # Full selectors, never flush or delete another rule just by priority.
            removed=subprocess.run(rule_command('del',args.address,args.network),capture_output=True,timeout=5)
            remaining=any(r.get('priority')==PRIORITY for r in read('ip','-j','rule','show'))
            emit({'event':'temporary_rule_removed','delete_completed':removed.returncode==0,'test_priority_absent':not remaining})
            if remaining:raise ValueError('Test priority still present; inspect before another action')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--seed-record',type=Path,default=DIAGNOSTIC,help='Acknowledged private USB provisioning result; never sends provisioning')
    parser.add_argument('--authorized-temporary-route',action='store_true',help='Only after explicit consent for this bounded host routing exception')
    parser.add_argument('--route-capture-child',action='store_true',help=argparse.SUPPRESS)
    for key in ('interface','hostname','address','network'):parser.add_argument('--'+key,help=argparse.SUPPRESS)
    parser.add_argument('--seconds',type=int,default=120)
    args=parser.parse_args()
    if not 10<=args.seconds<=120:parser.error('Duration10..120s')
    if args.route_capture_child:
        def interrupted(signum,frame):raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,interrupted)
        try:route_capture(args)
        except KeyboardInterrupt:pass
        except Exception as error:raise SystemExit('Route test stopped: '+type(error).__name__) from None
        return
    if os.geteuid()==0:parser.error('Start WITHOUT sudo; only the limited child needs sudo')
    net=json.loads((observer.LAB/'network.json').read_text())
    active=read('ip','-j','address','show','dev',net['interface'])
    prefix=next(a['prefixlen'] for dev in active for a in dev.get('addr_info',[]) if a.get('local')==net['address'])
    network=str(ipaddress.ip_network(net['address']+'/'+str(prefix),strict=False))
    check_scope(net['interface'],net['address'],network)
    if args.plan or not args.authorized_temporary_route:
        print('Plan verificado: prioridad5100; sólo origen LAN del gateway hacia su subred Wi-Fi, TCP origen8443, tabla main; temporal120s y retirada de la regla exacta. Sin cambios ejecutados.')
        return
    if not sys.stdin.isatty():parser.error('Normal interactive terminal required')
    if not seed_is_recent(json.loads(args.seed_record.read_text()),dt.datetime.now(dt.timezone.utc),args.seconds):
        raise SystemExit('El último UTC USB no deja margen para esta prueba. Sin cambios de rutas ni nueva provisión; revisar confianza temporal antes de seguir.')
    with socket.create_connection((net['address'],8443),timeout=3):pass
    print('Se aplicará sólo la regla temporal autorizada para respuestas del gateway. No se modifica configuración persistente ni ajustes de Tailscale.',flush=True)
    if subprocess.run(['sudo','-v']).returncode:raise SystemExit('Not started')
    os.umask(0o077)
    out=Path(tempfile.mkdtemp(prefix='m2-route-check-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=observer.ROOT/'results'))
    print('Resultados: '+str(out),flush=True)
    trace=observer.ROOT/'results/m2-phase-a-20261017T220757Z/gateway-events.jsonl';offset=trace.stat().st_size if trace.exists() else 0
    command=['sudo','-n',str(Path(sys.executable).resolve()),str(Path(__file__).resolve()),'--route-capture-child','--seconds',str(args.seconds),'--interface',net['interface'],'--hostname',net['hostname'],'--address',net['address'],'--network',network]
    events=[];result={'status':'running','events':events,'flash_performed':False,'provision_performed':False,'serial_port_opened':False,'tls_verified_by_capture':False,'temporary_host_routing_exception':True,'persistent_settings_changed':False,'raw_packets_saved':False,'board_identifiers_saved':False}
    process=None
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            value=json.loads(line);events.append(value)
            if value.get('event')=='capture_ready':print('LISTO: pulsá BOOT brevemente (menos de1s) y soltalo, una sola vez. No abrir monitores ni desconectar USB.',flush=True)
            elif value.get('event')=='temporary_rule_removed':print('Regla temporal retirada: '+str(value.get('test_priority_absent')),flush=True)
        code=process.wait()
        cleanup=any(e.get('event')=='temporary_rule_removed' and e.get('test_priority_absent') for e in events)
        result['temporary_rule_cleanup_confirmed']=cleanup
        result['status']='diagnostic_collected' if code==0 and cleanup else 'partial'
    except (Exception,KeyboardInterrupt):
        result['status']='partial'
        if process is not None:
            try:
                process.send_signal(signal.SIGINT)
                rest,_=process.communicate(timeout=15)
                events.extend(json.loads(line) for line in rest.splitlines() if line.strip())
            except (ProcessLookupError,PermissionError,subprocess.TimeoutExpired):pass
            result['temporary_rule_cleanup_confirmed']=any(e.get('event')=='temporary_rule_removed' and e.get('test_priority_absent') for e in events)
    finally:
        if trace.exists():
            with trace.open('rb') as stream:
                stream.seek(offset);rows=[json.loads(line) for line in stream.read(65536).splitlines()]
            keys={'sequence','host_epoch','http_status','conditional_request','peer_scope'}
            result['gateway_events']=[r for r in rows if set(r)==keys]
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('Estado: '+result['status']+'. Resultados: '+str(out),flush=True)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:raise SystemExit('Prueba interrumpida; verificar la retirada de la regla temporal en Resultados.') from None
    except Exception as error:raise SystemExit('Prueba detenida: '+type(error).__name__+'. Sin carga ni provisión.') from None
