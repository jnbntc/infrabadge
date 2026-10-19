#!/usr/bin/env python3
"""Bounded host network observation, without USB, firmware or provisioning access.

The normal-user parent reads only private network.json. A sudo child receives
only gateway hostname/address/interface and emits allowlisted packet metadata.
No promiscuous mode, pcap files, payload dumps, credentials or board identifiers.
"""
import argparse
import ctypes
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
LAB=Path('/var/home/juanb/.local/share/infrabadge-lab/phase-a-20261017T220757Z')
# AF_PACKET/SOCK_DGRAM presents IPv4 at offset0. Limit packets in the kernel:
# DNS5353: at most1500 bytes; TCP8443: only128 header bytes; everything else:0.
FILTER=[(0x30,0,0,0),(0x54,0,0,0xf0),(0x15,0,13,0x40),
        (0x30,0,0,9),(0x15,1,0,17),(0x15,5,10,6),
        (0xb1,0,0,0),(0x48,0,0,0),(0x15,9,0,5353),
        (0x48,0,0,2),(0x15,7,5,5353),
        (0xb1,0,0,0),(0x48,0,0,0),(0x15,3,0,8443),
        (0x48,0,0,2),(0x15,1,0,8443),
        (0x06,0,0,0),(0x06,0,0,128),(0x06,0,0,1500)]


def dns_name(data,offset):
    labels=[];seen=set();end=None
    for _ in range(64):
        if offset>=len(data) or offset in seen:raise ValueError('DNS bounds')
        seen.add(offset);length=data[offset]
        if length&0xc0==0xc0:
            if offset+1>=len(data):raise ValueError('DNS pointer')
            if end is None:end=offset+2
            offset=((length&0x3f)<<8)|data[offset+1];continue
        offset+=1
        if not length:return '.'.join(labels).lower(),end if end is not None else offset
        if length>63 or offset+length>len(data):raise ValueError('DNS label')
        labels.append(data[offset:offset+length].decode('ascii'));offset+=length
    raise ValueError('DNS complexity')


def packet_event(data,hostname,address):
    """Return closed enums/booleans/numbers only; never packet text or addresses."""
    try:
        if len(data)<20 or data[0]>>4!=4:return None
        ihl=(data[0]&15)*4
        if ihl<20 or len(data)<ihl+8 or struct.unpack_from('!H',data,6)[0]&0x1fff:return None
        total=struct.unpack_from('!H',data,2)[0]
        if total<ihl+8:return None
        source=socket.inet_ntoa(data[12:16]);destination=socket.inet_ntoa(data[16:20])
        src,dst=struct.unpack_from('!HH',data,ihl)
        if data[9]==6:
            if not ((source==address and src==8443) or (destination==address and dst==8443)) or source==destination:return None
            if len(data)<ihl+20:return None
            tcp_header=(data[ihl+12]>>4)*4
            if tcp_header<20 or ihl+tcp_header>total:return None
            flags=data[ihl+13]
            return {'event':'tcp','direction':'from_gateway' if source==address else 'to_gateway',
                    'syn':bool(flags&2),'ack':bool(flags&16),'fin':bool(flags&1),'rst':bool(flags&4),
                    'payload_bytes':total-ihl-tcp_header}
        if data[9]!=17 or 5353 not in (src,dst):return None
        dns=data[ihl+8:min(total,len(data))]
        if len(dns)<12:return None
        _,flags,questions,answers,authority,additional=struct.unpack_from('!6H',dns)
        if questions>32 or answers+authority+additional>128:return None
        offset=12;target=False;types=[]
        for _ in range(questions):
            name,offset=dns_name(dns,offset)
            kind,klass=struct.unpack_from('!HH',dns,offset);offset+=4
            if name==hostname.lower() and klass&0x7fff==1:
                target=True;types.append(kind)
        correct=other=False;matching=0
        for _ in range(answers+authority+additional):
            name,offset=dns_name(dns,offset)
            kind,klass,ttl,length=struct.unpack_from('!HHIH',dns,offset);offset+=10
            if offset+length>len(dns):return None
            if name==hostname.lower() and kind==1 and klass&0x7fff==1 and length==4:
                target=True;matching+=1
                if socket.inet_ntoa(dns[offset:offset+4])==address:correct=True
                else:other=True
            offset+=length
        if not target:return None
        if not flags&0x8000:
            if source==address:return None
            return {'event':'mdns_query_external','asks_ipv4':1 in types or 255 in types,'asks_ipv6':28 in types or 255 in types}
        return {'event':'mdns_reply','from_gateway_host':source==address,'contains_expected_ipv4':correct,'contains_other_ipv4':other,'matching_ipv4_records':matching}
    except (ValueError,UnicodeError,struct.error,IndexError):return None


def attach_filter(channel):
    class Instruction(ctypes.Structure):
        _fields_=[('code',ctypes.c_ushort),('jt',ctypes.c_ubyte),('jf',ctypes.c_ubyte),('k',ctypes.c_uint32)]
    class Program(ctypes.Structure):
        _fields_=[('length',ctypes.c_ushort),('instructions',ctypes.POINTER(Instruction))]
    rows=(Instruction*len(FILTER))(*(Instruction(*row) for row in FILTER))
    program=Program(len(rows),rows)
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.setsockopt(channel.fileno(),socket.SOL_SOCKET,26,ctypes.byref(program),ctypes.sizeof(program)):
        raise OSError(ctypes.get_errno(),'capture filter unavailable')


def capture(args):
    if os.geteuid()!=0:raise SystemExit('El hijo de captura necesita privilegio de lectura AF_PACKET.')
    ipaddress.IPv4Address(args.address)
    # ETH_P_ALL is necessary for Linux outgoing taps; the cBPF version/port
    # filter still restricts the data delivered to this process to relevant IPv4.
    with socket.socket(socket.AF_PACKET,socket.SOCK_DGRAM,socket.htons(0x0003)) as channel:
        attach_filter(channel);channel.bind((args.interface,0));channel.settimeout(.5)
        print(json.dumps({'event':'capture_ready','seconds':args.seconds}),flush=True)
        deadline=time.monotonic()+args.seconds;count=0
        while time.monotonic()<deadline and count<2000:
            try:data=channel.recv(1500)
            except socket.timeout:continue
            event=packet_event(data,args.hostname,args.address)
            if event:
                event['host_elapsed_ms']=round((time.monotonic()-(deadline-args.seconds))*1000)
                print(json.dumps(event,separators=(',',':')),flush=True);count+=1
    print(json.dumps({'event':'capture_finished','emitted_events':count}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--interface',help=argparse.SUPPRESS);parser.add_argument('--hostname',help=argparse.SUPPRESS);parser.add_argument('--address',help=argparse.SUPPRESS)
    parser.add_argument('--seconds',type=int,default=120)
    args=parser.parse_args()
    if not 10<=args.seconds<=120:parser.error('Duración10..120 s')
    if args.capture_child:
        try:capture(args)
        except KeyboardInterrupt:pass
        except Exception as error:raise SystemExit('Captura detenida: '+type(error).__name__) from None
        return
    if os.geteuid()==0 or not sys.stdin.isatty():parser.error('Iniciar en terminal normal SIN sudo; sólo el hijo de captura usa sudo')
    os.umask(0o077)
    net=json.loads((LAB/'network.json').read_text())
    active=json.loads(subprocess.check_output(['ip','-j','address','show','dev',net['interface']],text=True))
    if not any(row.get('local')==net['address'] for device in active for row in device.get('addr_info',[])):
        raise SystemExit('La dirección LAN del laboratorio cambió; sin captura ni acceso a la placa.')
    try:
        with socket.create_connection((net['address'],8443),timeout=3):pass
    except OSError:raise SystemExit('El gateway no responde por TCP; dejarlo activo antes de la captura.') from None
    print('Observación de'+str(args.seconds)+' s, sin puerto serie ni escrituras en la placa. No se instala ni configura nada.',flush=True)
    print('sudo se solicita sólo para leer paquetes filtrados de mDNS/TCP del laboratorio, sin guardar payloads.',flush=True)
    if subprocess.run(['sudo','-v']).returncode:raise SystemExit('No se inició la captura.')
    out=Path(tempfile.mkdtemp(prefix='m2-network-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=ROOT/'results'))
    print('Resultados: '+str(out),flush=True)
    command=['sudo','-n',str(Path(sys.executable).resolve()),str(Path(__file__).resolve()),'--capture-child','--seconds',str(args.seconds),'--interface',net['interface'],'--hostname',net['hostname'],'--address',net['address']]
    events=[]
    result={'status':'running','capture_mode':'both_directions_ipv4_filtered','flash_performed':False,'provision_performed':False,'serial_port_opened':False,'hardware_pass_inferred':False,'raw_packets_saved':False,'board_identifiers_saved':False,'events':events}
    process=None
    try:
        process=subprocess.Popen(command,stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            value=json.loads(line)
            if value.get('event')=='capture_ready':
                print('LISTO: si la placa está dormida, pulsá BOOT brevemente (menos de1 s) y soltalo. No mantengas BOOT ni desconectes USB. No abras monitores.',flush=True)
            elif value.get('event') in ('tcp','mdns_query_external','mdns_reply'):
                events.append(value)
        code=process.wait();result['status']='diagnostic_collected' if code==0 else 'capture_failed'
    except (Exception,KeyboardInterrupt):
        result['status']='partial'
        if process is not None:
            try:process.terminate()
            except (ProcessLookupError,PermissionError):pass
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('Estado: '+result['status']+'. Resultados: '+str(out),flush=True)
        print('Sólo metadatos saneados. No inferir TLS válido, timer ni304 de esta captura.',flush=True)


if __name__=='__main__':main()
