import hashlib
import secrets
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from infrabadge_gateway.app import create_app, fixture
from infrabadge_gateway.models import Device, GatewayConfig, Snapshot

@pytest.fixture
def setup():
    token=secrets.token_urlsafe(32)
    config=GatewayConfig(devices={'badge-lab': Device(token_sha256=[hashlib.sha256(token.encode()).hexdigest()])}, enable_faults=True)
    now=[1800000000]
    client=TestClient(create_app(config,lambda:now[0]))
    return client, config, now, {'Authorization':'Bearer '+token}

def test_200_304_expiry_and_changed_state(setup):
    client,config,now,headers=setup;url='/api/v1/devices/badge-lab/status'
    first=client.get(url,headers=headers);assert first.status_code==200
    snapshot=Snapshot.model_validate(first.json());assert snapshot.status=='HEALTHY'
    tag=first.headers['etag'];assert len(tag)==66
    unchanged=client.get(url,headers={**headers,'If-None-Match':tag})
    assert unchanged.status_code==304 and unchanged.content==b''
    assert int(unchanged.headers['x-infrabadge-now'])==now[0]
    config.devices['badge-lab'].scenario='CRITICAL'
    critical=client.get(url,headers={**headers,'If-None-Match':tag})
    assert critical.status_code==200 and critical.headers['etag']!=tag
    assert critical.json()['status']=='CRITICAL'
    old_tag=critical.headers['etag'];now[0]+=1800
    renewed=client.get(url,headers={**headers,'If-None-Match':old_tag})
    assert renewed.status_code==200 and renewed.json()['generated_at']==now[0]

def test_authentication_binding_and_rotation(setup):
    client,config,now,headers=setup;url='/api/v1/devices/badge-lab/status'
    assert client.get(url).status_code==401
    assert client.get(url,headers={'Authorization':'Bearer '+'x'*43}).status_code==401
    assert client.get('/api/v1/devices/other/status',headers=headers).status_code==401
    new=secrets.token_urlsafe(32);device=config.devices['badge-lab']
    device.token_sha256.append(hashlib.sha256(new.encode()).hexdigest())
    assert client.get(url,headers={'Authorization':'Bearer '+new}).status_code==200
    device.token_sha256.pop(0)
    assert client.get(url,headers=headers).status_code==401

@pytest.mark.parametrize('state',['HEALTHY','WARNING','CRITICAL','OFFLINE','UNKNOWN'])
def test_fixtures(state):
    snapshot=fixture('badge-lab',state,1800000000,1)
    assert Snapshot.model_validate_json(snapshot.model_dump_json())==snapshot
    assert len(snapshot.model_dump_json())<2048

@pytest.mark.parametrize('mutation',[{'schema_version':True},{'schema_version':1.0},{'simulated':1},{'schema_version':2},{'device_id':'bad/id'},{'expires_at':1799999999},
    {'simulated':None},{'alerts':[{'title':'x'*25,'detail':'INVALID'}]}, {'extra':'not allowed'},
    {'counts':{'healthy':0,'warning':0,'critical':1,'unknown':0}}])
def test_invalid_models(mutation):
    value=fixture('badge-lab','HEALTHY',1800000000,1).model_dump();value.update(mutation)
    with pytest.raises(ValidationError):Snapshot.model_validate(value)

@pytest.mark.parametrize('fault,code',[('json',200),('oversize',200),('expired',200),('version',200),('auth',401),('http',503)])
def test_explicit_lab_faults(setup,fault,code):
    client,config,now,headers=setup
    response=client.get('/api/v1/devices/badge-lab/status',params={'fault':fault},headers=headers)
    assert response.status_code==code
    if fault=='oversize':assert len(response.content)>2048
    if fault=='json':
        with pytest.raises(ValueError):response.json()
    if fault=='expired':assert response.json()['expires_at']<now[0]
    config.enable_faults=False
    assert client.get('/api/v1/devices/badge-lab/status',params={'fault':fault},headers=headers).status_code==404


def test_device_fault_is_explicit_and_gated(setup):
    client,config,_,headers=setup
    config.devices['badge-lab'].fault='json'
    response=client.get('/api/v1/devices/badge-lab/status',headers=headers)
    assert response.content==b'{broken'
    config.enable_faults=False
    assert client.get('/api/v1/devices/badge-lab/status',headers=headers).status_code==404
