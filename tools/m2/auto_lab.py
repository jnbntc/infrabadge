"""Synthetic M2 automation lab; no USB, routing or implicit startup on import."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import threading
import time

CASES=[('healthy',0,0),('unchanged',0,0),('warning',2,0),('critical',3,0),('unknown',4,0),('healthy',5,0),
 ('http',6,6),('recover',5,0),('auth',8,7),('recover',5,0),('json',10,8),('recover',5,0),
 ('oversize',12,9),('recover',5,0),('expired',14,10),('recover',5,0),('foreign_ca',16,5),('recover',5,0),
 ('wrong_san',18,5),('recover',5,0),('expired_cert',20,5),('recover',5,0),('dns',22,4),('recover',5,0),('wifi',24,3),('recover',5,0)]


def certificates(folder,hostname,run):
    """Sign all variants now, discard both root private keys on return."""
    import datetime as dt
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    folder=Path(folder);now=dt.datetime.now(dt.timezone.utc)
    def root(label):
        key=ec.generate_private_key(ec.SECP256R1());name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,label)])
        cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(days=2)).not_valid_after(now+dt.timedelta(days=3)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),critical=False).add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True).sign(key,hashes.SHA256())
        return key,cert
    key,ca=root('InfraBadge auto '+run[:8]);other_key,other=root('InfraBadge foreign '+run[:8])
    def write(name,data):
        with (folder/name).open('xb') as stream:stream.write(data)
        (folder/name).chmod(0o600)
    write('ca.pem',ca.public_bytes(serialization.Encoding.PEM))
    for kind in ('good','foreign_ca','wrong_san','expired_cert'):
        parent=other if kind=='foreign_ca' else ca;signer=other_key if kind=='foreign_ca' else key
        leaf_key=ec.generate_private_key(ec.SECP256R1());host='wrong.invalid' if kind=='wrong_san' else hostname
        leaf=x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,host)])).issuer_name(parent.subject).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-dt.timedelta(days=2)).not_valid_after(now-dt.timedelta(days=1) if kind=='expired_cert' else now+dt.timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]),critical=False).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signer.public_key()),critical=False).add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),critical=True).add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False).sign(signer,hashes.SHA256())
        write(kind+'.pem',leaf.public_bytes(serialization.Encoding.PEM));write(kind+'.key',leaf_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    return hashlib.sha256((folder/'ca.pem').read_bytes()).hexdigest()


def create_case_app(device_id,token_hash,slot,events,lock):
    from fastapi import Request
    from infrabadge_gateway.app import create_app
    from infrabadge_gateway.models import Device,GatewayConfig
    names={2:'WARNING',3:'CRITICAL',4:'UNKNOWN'};faults={6:'http',8:'auth',10:'json',12:'oversize',14:'expired'}
    config=GatewayConfig(devices={device_id:Device(token_sha256=[token_hash],scenario=names.get(slot,'HEALTHY'),fault=faults.get(slot))},enable_faults=slot in faults)
    app=create_app(config)
    @app.middleware('http')
    async def trace(request:Request,call_next):
        reply=await call_next(request)
        if request.url.path=='/api/v1/devices/'+device_id+'/status':
            with lock:events.append({'slot':slot,'http':reply.status_code,'conditional':bool(request.headers.get('if-none-match')),'host_epoch':int(time.time())})
        return reply
    return app


class Lab:
    def __init__(self,private,network,device):
        self.private=Path(private);self.network=network;self.device=device;self.events=[];self.lock=threading.Lock();self.servers=[];self.sockets=[];self.thread=None;self.error=None
    def start(self):
        import uvicorn
        slots=sorted({slot for _,slot,_ in CASES if slot not in (22,24)}|{31})
        try:
            for slot in slots:
                kind={16:'foreign_ca',18:'wrong_san',20:'expired_cert'}.get(slot,'good')
                listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind((self.network['address'],8443+slot));listener.listen(8);self.sockets.append(listener)
                app=create_case_app(self.device['device_id'],hashlib.sha256(self.device['token'].encode()).hexdigest(),slot,self.events,self.lock)
                server=uvicorn.Server(uvicorn.Config(app,ssl_certfile=str(self.private/(kind+'.pem')),ssl_keyfile=str(self.private/(kind+'.key')),lifespan='off',access_log=False,log_level='critical'))
                self.servers.append(server)
            async def serve():await asyncio.gather(*(server.serve(sockets=[sock]) for server,sock in zip(self.servers,self.sockets)))
            def worker():
                try:asyncio.run(serve())
                except Exception as error:self.error=type(error).__name__
            self.thread=threading.Thread(target=worker,daemon=True);self.thread.start();end=time.monotonic()+8
            while time.monotonic()<end and self.thread.is_alive() and not all(s.started for s in self.servers):time.sleep(.05)
            if not all(s.started for s in self.servers):raise RuntimeError('lab_start_failed')
            context=ssl.create_default_context(cafile=str(self.private/'ca.pem'))
            context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
            with socket.create_connection((self.network['address'],8443),timeout=3) as raw:
                with context.wrap_socket(raw,server_hostname=self.network['hostname']):pass
        except Exception:self.stop();raise
    def terminal_seen(self):
        with self.lock:return any(e['slot']==31 and e['http']==200 for e in self.events)
    def stop(self):
        for server in self.servers:server.should_exit=True
        if self.thread:self.thread.join(10)
        for sock in self.sockets:sock.close()
        return self.thread is None or not self.thread.is_alive()
