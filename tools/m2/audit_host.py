#!/usr/bin/env python3
"""Verify an existing host gateway and export a separate private phone bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import zipfile
from urllib.parse import urlsplit
from check_gateway import check
from phase_a import ROOT,save

def audit(private,out,make_bundle=True):
    net=json.loads((private/'network.json').read_text());address=net['address'];hostname=net['hostname']
    system={p[4][0] for p in socket.getaddrinfo(hostname,8443,type=socket.SOCK_STREAM)}
    mdns={}
    # Records from the local resolver can be synthetic. Report this separately;
    # a host answer is not evidence of multicast reachability on the phone.
    raw=subprocess.check_output(['resolvectl','--json=short','--type=A','query','--protocol=mdns','--interface='+net['interface'],hostname],text=True)
    for line in raw.splitlines():
        row=json.loads(line)
        if row.get('key',{}).get('name','').rstrip('.')==hostname and len(row.get('address',[]))==4:mdns['.'.join(map(str,row['address']))]=True
    if address not in mdns:raise ValueError('interface answer mismatch')
    report=check(private/'ca.pem',private/'client.json',interface_addresses=mdns)
    rejected=False
    try:
        with socket.create_connection((address,8443),timeout=3) as raw:
            with ssl.create_default_context().wrap_socket(raw,server_hostname=hostname):pass
    except ssl.SSLCertVerificationError:rejected=True
    if not rejected:raise ValueError('untrusted CA accepted')
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    import datetime as dt
    cert=x509.load_pem_x509_certificate((private/'server.pem').read_bytes());ca=x509.load_pem_x509_certificate((private/'ca.pem').read_bytes())
    now=dt.datetime.now(dt.timezone.utc)
    if not cert.not_valid_before_utc<=now<=cert.not_valid_after_utc:raise ValueError('certificate date')
    if hostname not in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName):raise ValueError('SAN mismatch')
    save(out/'host-lab-verification.json',{'status':'passed_tls_host_interface','tls_version':report['tls_version'],'http_200':True,'http_304':True,'auth_401':True,'ca_unknown_rejected':True,'hostname_and_dates_verified':True,'system_resolver_matches_wifi':address in system,'interface_resolver_matches_wifi':True,'interface_answer_may_be_synthetic':True,'external_dns_proof':'pending','ca_sha256':report['ca_sha256'],'leaf_sha256':cert.fingerprint(hashes.SHA256()).hex(),'not_before_utc':cert.not_valid_before_utc.isoformat(),'not_after_utc':cert.not_valid_after_utc.isoformat(),'ca_not_after_utc':ca.not_valid_after_utc.isoformat(),'hardware_validated':False})
    if make_bundle:
        bundle=private/'phone-client.zip'
        # Rebuild only this explicitly generated export, never a firmware/factory backup.
        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(private/'ca.pem','ca.pem');archive.write(private/'client.json','client.json');archive.write(ROOT/'tools/m2/check_gateway.py','check_gateway.py')
        bundle.chmod(0o600)
    save(out/'phase-a-status.json',{'status':'waiting_external_client','gateway_running':True,'host_tls_200_304_401':'passed','host_system_dns_wifi_mismatch':address not in system,'external_client_seen':False,'flash_performed':False,'provision_performed':False,'hardware_validated':False})
    print('PASS host: TLS1.2 con CA/SAN/fecha, 200/304/401 y rechazo de CA desconocida; conexión por interfaz, DNS externo todavía pendiente.')
    if make_bundle:print('Paquete PRIVADO para el cliente externo: '+str(bundle))
    print('SHA-256 CA pública: '+report['ca_sha256'])
    print('No se modificó DNS global ni se regeneraron credenciales/certificados. Placa sin acceder.')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private',type=Path,required=True);p.add_argument('--result',type=Path,required=True);a=p.parse_args()
    try:audit(a.private,a.result)
    except Exception as error:
        # Controlled messages contain no secret configuration values.
        print('Auditoría no completada: '+type(error).__name__)
        if type(error) is ValueError:print(str(error))
        raise SystemExit(1) from None
if __name__=='__main__':main()
