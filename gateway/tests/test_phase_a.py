"""Phase A tools with synthetic files/clients; no hardware, LAN or deployed secrets."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import pytest
from fastapi.testclient import TestClient
from infrabadge_gateway.models import Device,GatewayConfig
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
import phase_a
from phase_a_server import create_lab
from sanitize_logs import sanitize

def test_partition_digest(tmp_path):
    entry=struct.pack('<HBBII16sI',0x50aa,1,2,0x9000,0x6000,b'nvs',0)
    row=b'\xeb\xeb'+b'\xff'*14+hashlib.md5(entry).digest()
    path=tmp_path/'table.bin';path.write_bytes(entry+row+b'\xff'*32)
    assert phase_a.partitions(path)==[{'label':'nvs','type':1,'subtype':2,'offset':0x9000,'bytes':0x6000,'flags':0}]
    path.write_bytes(entry+row[:-1]+bytes([row[-1]^1]))
    with pytest.raises(ValueError):phase_a.partitions(path)

def test_log_export_discards_all_unrecognized_text():
    # A synthetic secret canary must never reach an exported field, even as suffix.
    value=sanitize('''I (1) infrabadge-m2: M2_BOOT: reset=8 wake=4; mock gateway only
I (2) infrabadge-m2: M2_DISPLAY: unchanged; live=1 clock=1
I (3) infrabadge-m2: M2_CYCLE: result=OK wifi_us=123 https_us=456 active_us=789 sleep_s=900
I (4) power: M1_SLEEP_ENTER: timer=900 s; BOOT/PWR wake; USB may disconnect
ssid=PRIVATE_CANARY
M2_DISPLAY: drawn; live=1 clock=1 PRIVATE_CANARY
Bearer PRIVATE_CANARY''')
    assert len(value['events'])==4 and value['discarded_lines']==3
    assert 'PRIVATE_CANARY' not in json.dumps(value)
    assert value['hardware_pass_inferred'] is False

def test_external_attestation_is_authenticated_and_separate(tmp_path):
    token='t'*43;digest=hashlib.sha256(token.encode()).hexdigest()
    config=GatewayConfig(devices={'phase-a-client':Device(token_sha256=[digest]),'badge-lab':Device(token_sha256=[hashlib.sha256(('r'*43).encode()).hexdigest()])})
    app=create_lab(config,digest,'ABCDEF','c'*64,tmp_path,'192.0.2.1')
    value=dict.fromkeys(['dns_expected_address','tls_explicit_ca','hostname_and_dates_verified','http_200','http_304','auth_401'],True)
    import time
    value.update(challenge='ABCDEF',ca_sha256='c'*64,client_epoch=int(time.time()),tls_version='TLSv1.2')
    client=TestClient(app,client=('192.0.2.9',1234))
    assert client.post('/phase-a/confirm',json=value).status_code==401
    assert not (tmp_path/'external-client.json').exists()
    headers={'Authorization':'Bearer '+token}
    assert client.post('/phase-a/confirm',json=dict(value,challenge='wrong'),headers=headers).status_code==400
    assert client.post('/phase-a/confirm',json=value,headers=headers).status_code==200
    output=(tmp_path/'external-client.json').read_text()
    assert json.loads(output)['external_client_seen'] is True
    assert '192.0.2.9' not in output and token not in output
    assert json.loads(output)['hardware_validated'] is False
    url='/api/v1/devices/badge-lab/status'
    client.get(url,headers={'Authorization':'Bearer PRIVATE_CANARY'})
    okay=client.get(url,headers={'Authorization':'Bearer '+'r'*43})
    assert okay.status_code==200
    assert client.get(url,headers={'Authorization':'Bearer '+'r'*43,'If-None-Match':okay.headers['etag']}).status_code==304
    trace=(tmp_path/'gateway-events.jsonl').read_text();rows=[json.loads(line) for line in trace.splitlines()]
    assert [row['http_status'] for row in rows]==[401,200,304]
    assert rows[-1]['conditional_request'] is True
    assert all(set(row)=={'sequence','host_epoch','http_status','conditional_request','peer_scope'} for row in rows)
    assert 'PRIVATE_CANARY' not in trace and '192.0.2.9' not in trace and 'Bearer' not in trace

def test_real_phase_a_client_with_explicit_ca(tmp_path):
    import threading,time,socket,uvicorn
    from infrabadge_gateway.lab import certificates
    from check_gateway import check
    ca,cert,key=certificates(tmp_path)
    token='t'*43;digest=hashlib.sha256(token.encode()).hexdigest()
    config=GatewayConfig(devices={'phase-a-client':Device(token_sha256=[digest])})
    ca_hash=hashlib.sha256(ca.read_bytes()).hexdigest()
    app=create_lab(config,digest,'ABCDEF',ca_hash,tmp_path,'127.0.0.1')
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(8)
    port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,ssl_certfile=str(cert),ssl_keyfile=str(key),lifespan='off',access_log=False,log_level='critical'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.01)
    assert server.started
    private=tmp_path/'client.json';private.write_text(json.dumps({'url':f'https://localhost:{port}','device_id':'phase-a-client','token':token,'expected_lan_address':'127.0.0.1'}));private.chmod(0o600)
    try:
        result=check(ca,private)
        assert result['http_200'] and result['http_304'] and result['auth_401']
        assert result['tls_version']=='TLSv1.2' and result['dns_scope']=='system'
        routed=check(ca,private,interface_addresses={'127.0.0.1'})
        assert routed['dns_scope']=='host_interface'
        wrong=json.loads(private.read_text());wrong['url']=f'https://wrong.invalid:{port}'
        private.write_text(json.dumps(wrong))
        import ssl
        with pytest.raises(ssl.SSLCertVerificationError):check(ca,private,interface_addresses={'127.0.0.1'})
        assert json.loads((tmp_path/'host-client.json').read_text())['external_client_seen'] is False
        assert not (tmp_path/'external-client.json').exists()
        private.chmod(0o644)
        with pytest.raises(ValueError):check(ca,private)
    finally:server.should_exit=True;thread.join(5);listener.close()
