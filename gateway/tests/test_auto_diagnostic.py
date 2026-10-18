"""Automation fixtures/report guards. No real board, routes or private lab access."""
import copy
import json
from pathlib import Path
import socket
import ssl
import struct
import sys
import threading
import time
import zlib
import pytest
import uvicorn
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
from auto_lab import CASES,certificates,create_case_app
from auto_report import FIELDS,validate
import automation
from auto_scope import authorization


def report():
    run='12345678'*4;events=[]
    for i,(_,_,error) in enumerate(CASES):
        events.append(dict(zip(FIELDS,[i,8 if i else 11,4 if i else 0,error,503 if i==6 else 401 if i==8 else 304 if i==1 else 0 if error else 200,1,int(error==0),0 if i==1 else 1,0 if i==1 else 1,1,0 if i==25 else 120 if error else 60,100,100,1000])))
    value={'version':1,'run':run,'phase':3,'fault':0,'count':26,'timer_returns':25,'checksum':0,'events':events}
    seal(value);return value


def seal(value):
    words=[0x49424d41,1]+[int(value['run'][i:i+8],16) for i in range(0,32,8)]+[value[k] for k in ('phase','fault','count','timer_returns')]+[0]
    words.extend(e[k] for e in value['events'] for k in FIELDS)
    words.extend([0]*(14*(26-len(value['events']))))
    value['checksum']=zlib.crc32(struct.pack('<'+'I'*len(words),*words))


def test_full_synthetic_report_is_explicitly_not_full_physical_m2_pass():
    value=report();result=validate(value,value['run'])
    assert result['status']=='diagnostic_cases_confirmed' and result['timer_reset_wake_confirmed']
    assert not result['full_m2_validation'] and not result['optical_display_validated']
    assert result['current_measurements']=='deferred_by_user'


@pytest.mark.parametrize('field,bad', [('reset',11),('wake',2),('clock',0),('transfers',1),('http',200),('display',2)])
def test_invalid_timer_or_frame_result_cannot_pass_even_with_valid_crc(field,bad):
    value=report();value['events'][1][field]=bad;seal(value)
    assert validate(value,value['run'])['status']=='incomplete_or_failed'


def test_corrupt_run_unknown_field_and_incomplete_are_rejected_or_not_passed():
    value=report()
    with pytest.raises(ValueError):validate(value,'0'*32)
    value['events'][0]['active_ms']+=1
    with pytest.raises(ValueError,match='checksum'):validate(value,value['run'])
    value=report();value['credential']='CANARY'
    with pytest.raises(ValueError,match='schema'):validate(value,value['run'])
    value=report();value.update(phase=4,fault=3,count=2,timer_returns=1,events=value['events'][:2]);seal(value)
    assert validate(value,value['run'])['status']=='incomplete_or_failed'


def test_range_rule_is_bounded_and_delete_matches_add():
    add=automation.range_rule('add','192.0.2.1','192.0.2.0/24');delete=automation.range_rule('del','192.0.2.1','192.0.2.0/24')
    assert add[3:]==delete[3:] and add[add.index('sport')+1]=='8443-8474'
    assert '192.0.2.1/32' in add and 'tcp' in add and add[-1]=='main'
    with pytest.raises(ValueError):automation.range_rule('add','198.51.100.1','192.0.2.0/24')


def test_root_window_removes_exact_rule_when_interrupted(monkeypatch):
    from types import SimpleNamespace
    calls=[];events=[]
    monkeypatch.setattr(automation.os,'geteuid',lambda:0)
    monkeypatch.setattr(automation.route,'check_scope',lambda *args:None)
    monkeypatch.setattr(automation.route,'reply_route',lambda *args:'wlan-test')
    monkeypatch.setattr(automation.route,'read',lambda *args:[])
    monkeypatch.setattr(automation.route,'emit',events.append)
    monkeypatch.setattr(automation.signal,'signal',lambda *args:None)
    def run(command,**kwargs):
        calls.append(command);return SimpleNamespace(returncode=0)
    monkeypatch.setattr(automation.subprocess,'run',run)
    def stop(_):raise KeyboardInterrupt
    monkeypatch.setattr(automation.time,'sleep',stop)
    args=SimpleNamespace(interface='wlan-test',address='192.0.2.1',network='192.0.2.0/24')
    with pytest.raises(KeyboardInterrupt):automation.root_window(args)
    assert calls==[automation.range_rule(action,args.address,args.network) for action in ('add','del')]
    assert events[-1]['priority_absent'] and events[-1]['delete_completed']


def test_attempted_manifest_is_rejected_before_board_network_or_sudo(monkeypatch,tmp_path):
    monkeypatch.setattr(automation.os,'geteuid',lambda:1000)
    monkeypatch.setattr(automation.sys,'stdin',type('Terminal',(),{'isatty':lambda self:True})())
    monkeypatch.setattr(automation,'validate_manifest',lambda path:{})
    (tmp_path/'execution.json').write_text('{}')
    with pytest.raises(ValueError,match='already_attempted'):automation.execute(tmp_path)


def test_repeat_guard_message_is_clear_and_other_exception_values_stay_private():
    message=automation.stop_message(ValueError('manifest_already_attempted_no_retry'))
    assert 'ya fue intentado' in message and 'No se inició otra carga' in message
    assert 'PRIVATE_CANARY' not in automation.stop_message(ValueError('PRIVATE_CANARY'))


def test_setup_only_scope_cannot_authorize_a_flash():
    assert authorization('setup_existing')=={'app_writes':0,'setups':1,'exports':1,'restore_firmware':False,'usb_resets':1}
    assert authorization('load_setup')['app_writes']==1
    with pytest.raises(ValueError):authorization('force_retry')


@pytest.mark.parametrize('matching_board',[True,False])
def test_setup_existing_resets_once_and_never_calls_flash(monkeypatch,tmp_path,matching_board):
    import hashlib
    import types
    import auto_sdk
    calls=[];previous=report();previous_bytes=json.dumps(previous).encode()
    (tmp_path/'previous-report.json').write_bytes(previous_bytes)
    (tmp_path/'firmware').mkdir();image=b'fixture-image';(tmp_path/'firmware/infrabadge.bin').write_bytes(image)
    manifest={'run':'abcdef12'*4,'execution_mode':'setup_existing','authorization':authorization('setup_existing'),
      'previous_journal_sha256':hashlib.sha256(previous_bytes).hexdigest(),
      'application':{'bytes':len(image),'sha256':hashlib.sha256(image).hexdigest()}}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(manifest))
    (tmp_path/'host-preflight.json').write_text(json.dumps({'utc_checked_epoch':time.time()}))
    monkeypatch.setattr(auto_sdk.sys,'argv',['auto_sdk','--approved-manifest',str(path),'--action','setup-existing','--out',str(tmp_path)])
    monkeypatch.setattr(auto_sdk.os,'geteuid',lambda:1000);monkeypatch.setenv('IDF_PATH','/synthetic-sdk')
    monkeypatch.setattr(auto_sdk.subprocess,'check_output',lambda *a,**k:auto_sdk.SDK+'\n')
    def forbidden(*a,**k):raise AssertionError('flashing path forbidden in setup-only')
    monkeypatch.setattr(auto_sdk.subprocess,'run',forbidden);monkeypatch.setattr(auto_sdk.first,'flash_command',forbidden)
    monkeypatch.setattr(auto_sdk,'port_wait',lambda *a:'/synthetic-usb')
    monkeypatch.setattr(auto_sdk.tempfile,'gettempdir',lambda:str(tmp_path))
    monkeypatch.setattr(auto_sdk.time,'sleep',lambda *a:None)
    monkeypatch.setattr(auto_sdk,'read_private',lambda path:{})
    class Channel:
        def __init__(self,**kwargs):pass
        def open(self):calls.append('open')
        def close(self):calls.append('close')
        def flush(self):pass
        def write(self,data):calls.append('setup' if data.startswith(b'IBAUTO1 ') else 'export')
    serial=types.ModuleType('serial');serial.Serial=Channel
    serial_tools=types.ModuleType('serial.tools');serial_tools.list_ports=types.SimpleNamespace(comports=lambda:[])
    reset=types.ModuleType('esptool.reset')
    def reset_factory(channel,uses_usb):
        assert uses_usb
        return lambda:calls.append('reset')
    reset.HardReset=reset_factory
    monkeypatch.setitem(sys.modules,'serial',serial);monkeypatch.setitem(sys.modules,'serial.tools',serial_tools)
    monkeypatch.setitem(sys.modules,'esptool.reset',reset)
    observed=copy.deepcopy(previous)
    if not matching_board:observed['run']='f'*32;seal(observed)
    monkeypatch.setattr(auto_sdk,'lines',lambda *args:iter(['IBAUTO_REPORT '+json.dumps(observed),'IBAUTO_OK']))
    assert auto_sdk.main()==(0 if matching_board else 1)
    saved=json.loads((tmp_path/'setup-existing.json').read_text())
    assert not saved['flash_attempted'] and calls.count('reset')==1
    assert calls.count('setup')==(1 if matching_board else 0)


def test_report_bounds_match_device_journal():
    value=report();value['events'][1]['active_ms']=3600001;seal(value)
    assert validate(value,value['run'])['status']=='incomplete_or_failed'
    value=report();value['timer_returns']=27;seal(value)
    with pytest.raises(ValueError,match='count'):validate(value,value['run'])
    with pytest.raises(ValueError,match='identity'):validate(report(),['x']*32)


def test_case_endpoints_authentication_and_faults_are_isolated():
    import hashlib
    token='synthetic-token-'+'x'*32;digest=hashlib.sha256(token.encode()).hexdigest();events=[];lock=threading.Lock()
    for slot,expected in [(0,200),(6,503),(8,401),(10,200),(12,200),(14,200),(31,200)]:
        client=TestClient(create_case_app('auto-test',digest,slot,events,lock))
        url='/api/v1/devices/auto-test/status'
        assert client.get(url).status_code==401
        answer=client.get(url,headers={'Authorization':'Bearer '+token})
        assert answer.status_code==expected
        if slot==10:
            with pytest.raises(ValueError):answer.json()
        if slot==12:assert len(answer.content)>2048
        if slot==14:assert answer.json()['expires_at']<int(time.time())
    assert token not in json.dumps(events) and all(set(e)=={'slot','http','conditional','host_epoch'} for e in events)


def test_generated_cert_variants_isolate_ca_san_and_dates_over_real_host_tls(tmp_path):
    certificates(tmp_path,'localhost','a'*32)
    context=ssl.create_default_context(cafile=str(tmp_path/'ca.pem'));context.minimum_version=context.maximum_version=ssl.TLSVersion.TLSv1_2
    from cryptography import x509
    assert {p.stem for p in tmp_path.glob('*.key')}=={'good','foreign_ca','wrong_san','expired_cert'}
    assert all(not x509.load_pem_x509_certificate((tmp_path/(kind+'.pem')).read_bytes()).extensions.get_extension_for_class(x509.BasicConstraints).value.ca for kind in ('good','foreign_ca','wrong_san','expired_cert'))
    for kind in ('good','foreign_ca','wrong_san','expired_cert'):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(8);port=listener.getsockname()[1]
        app=create_case_app('auto-test','0'*64,0,[],threading.Lock())
        server=uvicorn.Server(uvicorn.Config(app,ssl_certfile=str(tmp_path/(kind+'.pem')),ssl_keyfile=str(tmp_path/(kind+'.key')),lifespan='off',access_log=False,log_level='critical'))
        worker=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);worker.start();end=time.monotonic()+5
        while not server.started and worker.is_alive() and time.monotonic()<end:time.sleep(.01)
        assert server.started
        def connect():
            with socket.create_connection(('127.0.0.1',port),timeout=3) as raw:
                with context.wrap_socket(raw,server_hostname='localhost'):pass
        try:
            if kind=='good':connect()
            else:
                with pytest.raises(ssl.SSLCertVerificationError) as error:connect()
                if kind=='wrong_san':assert error.value.verify_code==62
                if kind=='expired_cert':assert error.value.verify_code==10
        finally:server.should_exit=True;worker.join(5);listener.close()
