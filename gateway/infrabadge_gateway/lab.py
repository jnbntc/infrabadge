"""Create isolated lab TLS material. Never a production CA or public credential."""
import argparse
import datetime as dt
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

def certificates(folder,host='localhost',kind='valid'):
    folder=Path(folder);now=dt.datetime.now(dt.timezone.utc)
    key=ec.generate_private_key(ec.SECP256R1())
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'InfraBadge ephemeral lab CA')])
    ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(days=3))
        .not_valid_after(now+dt.timedelta(days=30)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False)
        .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True)
        .sign(key,hashes.SHA256()))
    server_key=ec.generate_private_key(ec.SECP256R1());host='wrong.invalid' if kind=='wronghost' else host
    try:sans=[x509.IPAddress(ipaddress.ip_address(host))]
    except ValueError:sans=[x509.DNSName(host)]
    cert=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,host)]))
        .issuer_name(name).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-dt.timedelta(days=2)).not_valid_after(now-dt.timedelta(days=1) if kind=='expired' else now+dt.timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName(sans),critical=False)
        .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),critical=False)
        .add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        .sign(key,hashes.SHA256()))
    paths=folder/'ca.pem',folder/'server.pem',folder/'server.key'
    for path,data in zip(paths,[ca.public_bytes(serialization.Encoding.PEM),cert.public_bytes(serialization.Encoding.PEM),
        server_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())]):
        with path.open('xb') as stream:stream.write(data)
        path.chmod(0o600)
    # CA private key deliberately not persisted: rotation creates a new lab CA and requires physical reprovisioning.
    return paths

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--hostname',required=True)
    p.add_argument('--device-id',default='badge-lab');p.add_argument('--port',type=int,default=8443)
    a=p.parse_args();root=Path(__file__).resolve().parents[2]
    output=a.output.expanduser().resolve()
    if output.is_relative_to(root) or output.exists():p.error('Usá una carpeta nueva, fuera del repositorio')
    if not re.fullmatch('[a-zA-Z0-9.-]{1,128}',a.hostname) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,31}',a.device_id) or not 1024<=a.port<=65535:
        p.error('Hostname, ID o puerto inválido')
    ssid=getpass.getpass('SSID privado (sin eco): ');password=getpass.getpass('Clave Wi-Fi (sin eco): ')
    if not ssid.isascii() or not 1<=len(ssid)<=32 or not password.isascii() or not 8<=len(password)<=63:p.error('SSID/clave fuera de límites')
    os.umask(0o077);output.mkdir(parents=True,mode=0o700)
    ca,_,_=certificates(output,a.hostname);token=secrets.token_urlsafe(32)
    gateway={'devices':{a.device_id:{'token_sha256':[hashlib.sha256(token.encode()).hexdigest()],'scenario':'HEALTHY'}},'enable_faults':False}
    device={'schema_version':1,'device_id':a.device_id,'ssid':ssid,'wifi_password':password,
        'gateway_url':f'https://{a.hostname}:{a.port}','token':token,'ca_pem':ca.read_text(),
        'interval_seconds':900,'wifi_timeout_ms':15000,'http_timeout_ms':5000}
    for name,value in [('gateway.json',gateway),('device.json',device)]:
        with (output/name).open('x') as stream:json.dump(value,stream,ensure_ascii=True,indent=2)
    print('Material de laboratorio creado en carpeta privada. No se abrió ningún puerto ni dispositivo.')
if __name__=='__main__':main()
