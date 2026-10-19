"""Actual loopback HTTPS and certificate validation; no ESP32/Wi-Fi claim."""
import datetime as dt
import hashlib
import ipaddress
import secrets
import socket
import ssl
import threading
import time
import httpx
import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from infrabadge_gateway.app import create_app
from infrabadge_gateway.models import Device, GatewayConfig

from infrabadge_gateway.lab import certificates

@pytest.fixture(params=['valid','expired','wronghost'])
def server(request,tmp_path):
    ca,cert,key=certificates(tmp_path,kind=request.param);token=secrets.token_urlsafe(32)
    config=GatewayConfig(devices={'badge-lab':Device(token_sha256=[hashlib.sha256(token.encode()).hexdigest()])})
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(8)
    port=listener.getsockname()[1]
    instance=uvicorn.Server(uvicorn.Config(create_app(config),ssl_certfile=str(cert),ssl_keyfile=str(key),
                                         lifespan='off',log_level='critical',access_log=False))
    thread=threading.Thread(target=instance.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not instance.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.01)
    assert instance.started,'Loopback HTTPS server did not start'
    try:yield request.param,ca,f'https://localhost:{port}',{'Authorization':'Bearer '+token}
    finally:
        instance.should_exit=True;thread.join(5);listener.close();assert not thread.is_alive()

def test_real_tls(server):
    kind,ca,url,headers=server
    context=ssl.create_default_context(cafile=str(ca))
    with httpx.Client(verify=context,trust_env=False,timeout=3) as client:
        if kind=='valid':
            first=client.get(url+'/api/v1/devices/badge-lab/status',headers=headers)
            assert first.status_code==200
            assert client.get(url+'/api/v1/devices/badge-lab/status',headers={**headers,'If-None-Match':first.headers['etag']}).status_code==304
            with httpx.Client(verify=ssl.create_default_context(),trust_env=False,timeout=3) as untrusted:
                with pytest.raises(httpx.ConnectError):untrusted.get(url+'/api/v1/devices/badge-lab/status',headers=headers)
        else:
            with pytest.raises(httpx.ConnectError):client.get(url+'/api/v1/devices/badge-lab/status',headers=headers)

def test_untrusted_ca_and_dns(monkeypatch):
    def fail(*args,**kwargs):raise socket.gaierror(socket.EAI_NONAME,'synthetic DNS failure')
    monkeypatch.setattr(socket,'getaddrinfo',fail)
    with httpx.Client(trust_env=False,timeout=1) as client:
        with pytest.raises(httpx.ConnectError):client.get('https://unresolvable.invalid/')
