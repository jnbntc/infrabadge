"""Pure host configuration tests: importing the tool never opens a serial port."""
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('provision',Path(__file__).resolve().parents[2]/'tools/m2/provision.py')
provision=importlib.util.module_from_spec(spec);spec.loader.exec_module(provision)

def test_wire_and_fresh_time(tmp_path):
    # Synthetic values only; no operational credential on disk or serial device.
    config={name:'SYNTHETIC' for name in provision.FIELDS};config['schema_version']=1
    config.update(interval_seconds=900,wifi_timeout_ms=15000,http_timeout_ms=5000)
    file=tmp_path/'device.json';file.write_text(json.dumps(config));file.chmod(0o600)
    value=provision.read_private(file);wire=provision.wire(value,1800000000)
    assert wire.startswith(b'IBPROV1 ') and wire.endswith(b'\n') and wire.count(b'\n')==1
    assert json.loads(wire[8:])['seed_utc']==1800000000
    assert 'seed_utc' not in value
    file.chmod(0o644)
    with pytest.raises(ValueError):provision.read_private(file)
    with pytest.raises(ValueError):provision.wire(value,0)
    with pytest.raises(ValueError):provision.wire(dict(value,ssid='x'*5000),1800000000)
    with pytest.raises(UnicodeError):provision.wire(dict(value,ssid='ñ'),1800000000)


@pytest.mark.parametrize('field,value', [
    ('wifi_timeout_ms',20000), ('wifi_timeout_ms',15001), ('wifi_timeout_ms',999),
    ('wifi_timeout_ms',True), ('wifi_timeout_ms',15000.0),
    ('http_timeout_ms',10001), ('interval_seconds',59), ('interval_seconds',3601),
])
def test_reject_firmware_limits_before_provision_frame(field,value):
    config=dict(interval_seconds=900,wifi_timeout_ms=15000,http_timeout_ms=5000)
    config[field]=value
    with pytest.raises(ValueError,match='firmware range'):
        provision.wire(config,1800000000)


@pytest.mark.parametrize('timeout',[1000,15000])
def test_supported_wifi_timeout_boundaries(timeout):
    config=dict(interval_seconds=900,wifi_timeout_ms=timeout,http_timeout_ms=5000)
    assert json.loads(provision.wire(config,1800000000)[8:])['wifi_timeout_ms']==timeout


def test_invalid_timeout_never_opens_serial(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock
    config={name:'SYNTHETIC' for name in provision.FIELDS}
    config.update(schema_version=1,interval_seconds=900,wifi_timeout_ms=20000,http_timeout_ms=5000)
    file=tmp_path/'invalid.json';file.write_text(json.dumps(config));file.chmod(0o600)
    serial_factory=Mock(side_effect=AssertionError('serial must not be opened'))
    monkeypatch.setitem(sys.modules,'serial',SimpleNamespace(Serial=serial_factory))
    monkeypatch.setattr(sys,'argv',['provision','--config',str(file),'--port','/dev/synthetic-unused','--confirm-trusted-host-time'])
    with pytest.raises(SystemExit):provision.main()
    serial_factory.assert_not_called()
