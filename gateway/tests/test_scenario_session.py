"""M2 manual scenario session with ASGI fixtures/fake route commands, no hardware."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import pytest
from fastapi.testclient import TestClient
from infrabadge_gateway.models import Device,GatewayConfig
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
import scenario_session as session
from phase_a_server import create_lab


def test_complete_sequence_authentication_and_original_config_unchanged(tmp_path):
    token='synthetic_token_canary_'+'x'*24;digest=hashlib.sha256(token.encode()).hexdigest()
    original=GatewayConfig(devices={'badge-lab':Device(token_sha256=[digest]),'phase-a-client':Device(token_sha256=['0'*64])})
    before=original.model_dump();config=copy.deepcopy(original)
    client=TestClient(create_lab(config,'0'*64,'unused','unused',tmp_path,'192.0.2.1'),client=('192.0.2.7',1234))
    headers={'Authorization':'Bearer '+token};etag=None
    for index in range(len(session.STAGES)):
        stage=session.apply_stage(config,index)
        assert client.get('/api/v1/devices/badge-lab/status').status_code==401
        request_headers=dict(headers)
        if etag:request_headers['If-None-Match']=etag
        reply=client.get('/api/v1/devices/badge-lab/status',headers=request_headers)
        assert reply.status_code in stage['expected_http']
        if not stage['fault']:
            if reply.status_code==200:assert reply.json()['status']==stage['scenario'] and reply.json()['simulated']
            else:assert index==len(session.STAGES)-1 and reply.status_code==304
            etag=reply.headers['etag']
        else:assert reply.status_code==503
    assert original.model_dump()==before and not config.enable_faults and config.devices['badge-lab'].scenario=='HEALTHY'
    trace=(tmp_path/'gateway-events.jsonl').read_text()
    assert token not in trace and '192.0.2.7' not in trace


def test_only_expected_external_gateway_events_count():
    row={'sequence':1,'host_epoch':1792290000,'http_status':200,'conditional_request':True,'peer_scope':'external_unattributed'}
    assert session.eligible_event(row,200)
    assert not session.eligible_event(dict(row,peer_scope='host'),200)
    assert not session.eligible_event(dict(row,http_status=304),200)
    assert not session.eligible_event(dict(row,secret='canary'),200)
    assert session.eligible_event(dict(row,http_status=304),[200,304])
    assert not session.eligible_event(dict(row,http_status=304,conditional_request=False),[200,304])


def test_custom_route_operation_failure_still_cleans_exact_rule(monkeypatch):
    route=session.route;commands=[];events=[]
    monkeypatch.setattr(route.os,'geteuid',lambda:0)
    monkeypatch.setattr(route,'check_scope',lambda *args:None)
    monkeypatch.setattr(route,'reply_route',lambda *args:'synthetic-wifi')
    monkeypatch.setattr(route,'read',lambda *args:[])
    monkeypatch.setattr(route,'emit',events.append)
    monkeypatch.setattr(route.signal,'signal',lambda *args:None)
    def run(command,**kwargs):commands.append(command);return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(route.subprocess,'run',run)
    def fail(args):raise RuntimeError('fixture')
    args=types.SimpleNamespace(address='192.0.2.1',network='192.0.2.0/24',interface='synthetic-wifi')
    with pytest.raises(RuntimeError):route.route_capture(args,operation=fail)
    assert [r[2] for r in commands]==['add','del'] and commands[0][3:]==commands[1][3:]
    assert events[-1]['test_priority_absent']
