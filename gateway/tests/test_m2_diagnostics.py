"""Regression for compiled-out INFO logs and strictly sanitized HTTP diagnostics."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/m2'))
from sanitize_logs import sanitize

spec=importlib.util.spec_from_file_location('verify_build',ROOT/'tools/verify_build.py')
verifier=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def test_warn_only_build_cannot_claim_m2_usb_logging():
    image=b'M2_BOOT: M2_DISPLAY: M2_CYCLE: M2_HTTP:'
    config={'LOG_DEFAULT_LEVEL':2,'LOG_MAXIMUM_LEVEL':3,'LOG_DYNAMIC_LEVEL_CONTROL':True}
    verifier.verify_m2_logging(config,image)
    with pytest.raises(AssertionError,match='INFO events'):
        verifier.verify_m2_logging(dict(config,LOG_MAXIMUM_LEVEL=2),image)
    with pytest.raises(AssertionError,match='INFO events'):
        verifier.verify_m2_logging(dict(config,LOG_MAXIMUM_LEVEL=4),image)
    with pytest.raises(AssertionError,match='per-tag'):
        verifier.verify_m2_logging(dict(config,LOG_DYNAMIC_LEVEL_CONTROL=False),image)
    for marker in image.split():
        with pytest.raises(AssertionError,match='Missing compiled'):
            verifier.verify_m2_logging(config,image.replace(marker,b''))


def test_http_diagnostic_exports_only_numeric_codes_and_closed_stage():
    line='I (123) infrabadge-m2: M2_HTTP: stage=TRANSFER esp=-1 tls=32769 detail=-9984 flags=4 http=-1 timeout=1'
    result=sanitize(line)
    assert result['events']==[{'event':'http','stage':'TRANSFER','esp':-1,'tls':32769,'detail':-9984,'flags':4,'http':-1,'timeout':True}]
    for bad in (line+' Bearer PRIVATE_CANARY',line.replace('TRANSFER','PRIVATE_CANARY'),line.replace('esp=-1','esp=2147483648'),line.replace('http=-1','http=-2')):
        exported=sanitize(bad)
        assert exported['events']==[] and exported['discarded_lines']==1
        assert 'PRIVATE_CANARY' not in str(exported)
