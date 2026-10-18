"""Safety and evidence checks for the physical runner, with no hardware or secrets."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/m2'))
import physical_first as first


def good_observations():
    return {'flash_completed': True, 'provision_attempted': True, 'provision_ack': True,
            'external_http_200_observed': True, 'operator_screen_confirmed': True,
            'unexpected_reset_or_panic': False,
            'events': [{'event': 'display', 'result': 'drawn', 'live': True, 'clock': True},
                       {'event': 'cycle', 'result': 'OK', 'sleep_s': 900}]}


def test_only_the_application_range_is_flashed():
    command = first.flash_command('/dev/synthetic', Path('/tmp/synthetic-app.bin'))
    assert command.count('write_flash') == 1
    assert command[-2:] == ['0x10000', '/tmp/synthetic-app.bin']
    assert not set(command) & {'erase_flash', 'erase_region', '--erase-all', '--force', '0x0', '0x8000'}
    start = command.index('write_flash')
    assert command[start + 1:-2] == ['--flash_mode', 'dio', '--flash_freq', '40m', '--flash_size', '8MB']
    # Rounded sector erase must remain inside the one MiB factory application slot.
    assert 0x10000 + ((853296 + 4095) // 4096) * 4096 <= 0x110000


def test_incomplete_write_blocks_another_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(first, 'ROOT', tmp_path)
    directory = tmp_path / 'results/m2-physical-first-synthetic'
    directory.mkdir(parents=True)
    record = directory / 'result.json'
    record.write_text(json.dumps({'app_sha256': first.APP_SHA, 'flash_attempted': False}))
    assert first.prior_write() is None
    # A timeout or interrupted attempt still blocks automatic retry.
    record.write_text(json.dumps({'app_sha256': first.APP_SHA, 'flash_attempted': True, 'flash_completed': False}))
    assert first.prior_write() == directory


def test_first_query_requires_independent_evidence():
    value = good_observations()
    assert first.query_supported(value)
    for field in ('flash_completed', 'provision_attempted', 'provision_ack', 'external_http_200_observed', 'operator_screen_confirmed'):
        partial = dict(value, **{field: False})
        assert not first.query_supported(partial)
    assert not first.query_supported(dict(value, events=[]))


def test_network_failure_bad_clock_or_reset_never_passes():
    for error in ('DNS', 'TLS', 'AUTH', 'CLOCK', 'WIFI', 'STORE'):
        value = good_observations()
        value['events'][-1]['result'] = error
        assert not first.query_supported(value)
    for field in ('clock', 'live'):
        value = good_observations()
        value['events'][0][field] = False
        assert not first.query_supported(value)
    assert not first.query_supported(dict(good_observations(), unexpected_reset_or_panic=True))


def test_setup_clock_cycle_does_not_hide_post_provision_result():
    value=good_observations()
    value['events'].insert(0,{'event':'cycle','result':'CLOCK','sleep_s':1800})
    value['provision_event_index']=1
    assert first.query_supported(value)
    value['events'][-1]['result']='HTTP'
    assert not first.query_supported(value)


def test_diagnostic_attempt_guard_is_separate_and_also_blocks_timeout(tmp_path,monkeypatch):
    import physical_diagnostic as diagnostic
    monkeypatch.setattr(diagnostic,'ROOT',tmp_path)
    out=tmp_path/'results/m2-physical-diagnostic-synthetic';out.mkdir(parents=True)
    (out/'result.json').write_text(json.dumps({'app_sha256':diagnostic.APP_SHA,'flash_attempted':True,'flash_completed':False}))
    assert diagnostic.previous_attempt()==out


def test_existing_nvs_setup_wake_has_one_flash_one_provision_no_secret_export(tmp_path,monkeypatch):
    import hashlib,sys,types
    app=tmp_path/'app.bin';app.write_bytes(b'synthetic firmware')
    digest=hashlib.sha256(app.read_bytes()).hexdigest()
    out=tmp_path/'results';out.mkdir()
    lab=tmp_path/'lab';lab.mkdir();trace=lab/'gateway-events.jsonl';trace.write_text('')
    monkeypatch.setattr(first,'PHASE_A',lab)
    monkeypatch.setenv('IDF_PATH','/synthetic-idf')
    monkeypatch.setattr(first.subprocess,'check_output',lambda *args,**kwargs:first.SDK+'\n')
    commands=[]
    def run(command,**kwargs):
        commands.append(command);return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(first.subprocess,'run',run)
    monkeypatch.setattr(first,'yes',lambda prompt:True)
    config={'schema_version':1,'device_id':'synthetic','ssid':'PRIVATE_SYNTHETIC_SSID',
            'wifi_password':'PRIVATE_SYNTHETIC_PASSWORD','token':'PRIVATE_SYNTHETIC_TOKEN',
            'ca_pem':'synthetic','gateway_url':'https://synthetic.invalid:8443',
            'interval_seconds':900,'wifi_timeout_ms':15000,'http_timeout_ms':5000}
    monkeypatch.setattr(first,'read_private',lambda path:config.copy())
    class Disconnected(OSError):pass
    lines=[b'I (1) infrabadge-m2: M2_CYCLE: result=CLOCK wifi_us=0 https_us=0 active_us=1 sleep_s=1800\n',
           b'I (2) power: M1_SLEEP_ENTER: timer=1800 s; BOOT/PWR wake; USB may disconnect\n',
           None,b'IBPROV_READY\n',b'IBPROV_OK\n',
           b'I (3) infrabadge-m2: M2_HTTP: stage=TRANSFER esp=0 tls=0 detail=0 flags=0 http=200 timeout=0\n',
           b'I (4) infrabadge-m2: M2_DISPLAY: drawn; live=1 clock=1\n',
           b'I (5) infrabadge-m2: M2_CYCLE: result=OK wifi_us=1 https_us=2 active_us=3 sleep_s=900\n',None]
    instances=[]
    class Channel:
        def __init__(self,**kwargs):self.sent=[];self.opens=0;instances.append(self)
        def open(self):self.opens+=1
        def close(self):pass
        def flush(self):pass
        def write(self,value):self.sent.append(value)
        def readline(self,size):
            line=lines.pop(0)
            if line is None:raise Disconnected()
            if b'result=OK ' in line:
                trace.write_text(json.dumps({'sequence':1,'host_epoch':1,'http_status':200,'conditional_request':False,'peer_scope':'external_unattributed'})+'\n')
            return line
    port=types.SimpleNamespace(vid=0x303a,pid=0x1001,device='/dev/null',serial_number='PRIVATE_SYNTHETIC_SERIAL')
    enumerations=iter([[port],[],[port]])
    serial=types.ModuleType('serial');serial.Serial=Channel;serial.SerialException=Disconnected
    tools=types.ModuleType('serial.tools');tools.list_ports=types.SimpleNamespace(comports=lambda:next(enumerations))
    monkeypatch.setitem(sys.modules,'serial',serial);monkeypatch.setitem(sys.modules,'serial.tools',tools)
    args=types.SimpleNamespace(results=str(out),port='/dev/null')
    assert first.physical(args,artifact_verifier=lambda:app,app_sha=digest,allow_setup_wake=True)==0
    result=json.loads((out/'result.json').read_text())
    assert result['setup_usb_reopened_once'] and result['first_query_functionally_supported']
    assert not result['deep_sleep_validated'] and not result['etag_304_validated']
    assert len(commands)==1 and commands[0][-2]=='0x10000'
    assert len(instances)==1 and instances[0].opens==2 and len(instances[0].sent)==1
    assert instances[0].sent[0].startswith(b'IBPROV1 ')
    for private in ('PRIVATE_SYNTHETIC_SSID','PRIVATE_SYNTHETIC_PASSWORD','PRIVATE_SYNTHETIC_TOKEN','PRIVATE_SYNTHETIC_SERIAL'):
        assert private not in (out/'result.json').read_text()
