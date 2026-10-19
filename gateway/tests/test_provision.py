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
