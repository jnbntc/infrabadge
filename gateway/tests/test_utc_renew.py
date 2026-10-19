"""Provision-only exchange with fake USB; no hardware, SDK or networking."""
from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
import renew_utc_route as renewal


class Channel:
    def __init__(self,lines):self.lines=iter(lines);self.sent=[]
    def readline(self,size):return next(self.lines,b'')
    def write(self,value):self.sent.append(value)
    def flush(self):pass


def test_sends_once_after_exact_ready_and_records_ack(monkeypatch,tmp_path):
    channel=Channel([b'private-canary\n',b'xIBPROV_READY\n',b'IBPROV_READY\n',b'IBPROV_READY\n',b'IBPROV_OK\n'])
    monkeypatch.setattr(renewal,'read_private',lambda path:{'mock':'private-canary'})
    monkeypatch.setattr(renewal,'wire',lambda value,epoch:b'private-payload')
    state={'provision_attempted':False,'provision_ack':False}
    renewal.exchange(channel,state,tmp_path/'result.json',clock=iter(range(8)).__next__,epoch=lambda:1792288800)
    assert channel.sent==[b'private-payload'] and state['provision_ack']
    assert 'private' not in (tmp_path/'result.json').read_text()


def test_unexpected_ack_never_sends_configuration(tmp_path):
    channel=Channel([b'IBPROV_OK\n'])
    with pytest.raises(renewal.first.StopTest,match='ack_without'):
        renewal.exchange(channel,{'provision_attempted':False},tmp_path/'result.json',clock=iter(range(5)).__next__)
    assert not channel.sent


def test_timeout_does_not_send_without_window(tmp_path):
    channel=Channel([b'IBPROV_READY suffix\n'])
    with pytest.raises(renewal.first.StopTest,match='not_observed'):
        renewal.exchange(channel,{'provision_attempted':False},tmp_path/'result.json',clock=iter([0,1,41]).__next__)
    assert not channel.sent


def test_prior_uncertain_write_blocks_another_invocation(tmp_path):
    folder=tmp_path/'m2-utc-renew-synthetic';folder.mkdir()
    (folder/'result.json').write_text(json.dumps({'provision_attempted':True,'provision_ack':False}))
    assert renewal.previous_attempt(tmp_path)==folder


def test_preflight_without_usb_write_does_not_consume_authorization(tmp_path):
    folder=tmp_path/'m2-utc-renew-synthetic';folder.mkdir()
    (folder/'result.json').write_text(json.dumps({'provision_attempted':False}))
    assert renewal.previous_attempt(tmp_path) is None
