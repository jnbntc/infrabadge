#!/usr/bin/env python3
"""External HTTPS client with explicit CA; secrets only in a private config file."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import socket
import ssl
import stat
import time
from urllib.parse import urlsplit

def check(ca,config,submit=True,interface_addresses=None):
    path=Path(config)
    if path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('private client file required')
    value=json.loads(path.read_text());origin=urlsplit(value['url'])
    if origin.scheme!='https' or origin.username or origin.password or origin.path or origin.query:raise ValueError('HTTPS origin required')
    context=ssl.create_default_context(cafile=str(ca));context.check_hostname=True
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.maximum_version=ssl.TLSVersion.TLSv1_2  # Match the current ESP32 M2 client.
    addresses=set(interface_addresses) if interface_addresses is not None else {entry[4][0] for entry in socket.getaddrinfo(origin.hostname,origin.port,type=socket.SOCK_STREAM)}
    if value['expected_lan_address'] not in addresses:raise ValueError('DNS does not contain expected LAN address')
    headers={'Authorization':'Bearer '+value['token']}
    connection=http.client.HTTPSConnection(origin.hostname,origin.port,timeout=5,context=context)
    if interface_addresses is not None:
        # Host-only route diagnostic, equivalent to curl --resolve: TLS SNI and
        # certificate hostname checks still use the URL hostname. Not exposed in
        # the phone CLI, whose DNS must work without a forced address.
        selected=value['expected_lan_address']
        connection._create_connection=lambda target,timeout,source_address=None: socket.create_connection((selected,target[1]),timeout,source_address)
    def get(path,extra=None):
        connection.request('GET',path,headers={**headers,**(extra or {})});response=connection.getresponse()
        body=response.read(4097)
        if len(body)>4096:raise ValueError('response limit')
        return response.status,dict((k.lower(),v) for k,v in response.getheaders()),body
    try:
        status,_,body=get('/phase-a/ready')
        if status!=200:raise ValueError('lab not ready')
        ready=json.loads(body);nonce=ready['challenge']
        tls_version=connection.sock.version()
        if tls_version!='TLSv1.2':raise ValueError('TLS version mismatch')
        endpoint='/api/v1/devices/'+value['device_id']+'/status'
        status,first_headers,body=get(endpoint)
        if status!=200 or not json.loads(body)['simulated']:raise ValueError('first response')
        tag=first_headers['etag'];status,_,body=get(endpoint,{'If-None-Match':tag})
        if status!=304 or body:raise ValueError('conditional response')
        connection.request('GET',endpoint);response=connection.getresponse();response.read()
        if response.status!=401:raise ValueError('authentication not enforced')
        report={'dns_expected_address':True,'tls_explicit_ca':True,'hostname_and_dates_verified':True,'http_200':True,'http_304':True,'auth_401':True,'tls_version':tls_version,'dns_scope':'host_interface' if interface_addresses is not None else 'system','challenge':nonce,'client_epoch':int(time.time()),'ca_sha256':hashlib.sha256(Path(ca).read_bytes()).hexdigest()}
        if submit:
            connection.request('POST','/phase-a/confirm',body=json.dumps(report).encode('ascii'),headers={**headers,'Content-Type':'application/json'})
            response=connection.getresponse();response.read()
            if response.status!=200:raise ValueError('confirmation rejected')
        return report
    finally:connection.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ca',type=Path,required=True);p.add_argument('--config',type=Path,required=True);a=p.parse_args()
    try:report=check(a.ca,a.config)
    except Exception:raise SystemExit('FAIL: revisar DNS/red, CA/SAN/fecha o archivo privado; no se desactivó TLS ni se muestran credenciales.') from None
    print('PASS cliente HTTPS TLS1.2: DNS, CA/SAN/fecha, 200, 304 y rechazo 401. Reto: '+report['challenge'])
if __name__=='__main__':main()
