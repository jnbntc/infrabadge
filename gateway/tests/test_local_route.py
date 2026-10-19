"""Temporary routing plan and cleanup with fake commands, no host mutation."""
from pathlib import Path
import sys
import types
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
import try_local_route as trial


def test_rule_only_matches_gateway_tcp_replies_and_delete_is_exact():
    add=trial.rule_command('add','192.0.2.1','192.0.2.0/24')
    assert add==['ip','rule','add','priority','5100','from','192.0.2.1/32','to','192.0.2.0/24','ipproto','tcp','sport','8443','lookup','main']
    delete=trial.rule_command('del','192.0.2.1','192.0.2.0/24')
    assert delete[:2]+delete[3:]==add[:2]+add[3:]
    assert not set(add)&{'flush','replace','route','tailscale','down'}
    with pytest.raises(ValueError):trial.rule_command('add','198.51.100.1','192.0.2.0/24')
    with pytest.raises(ValueError):trial.rule_command('flush','192.0.2.1','192.0.2.0/24')


def test_capture_error_still_removes_exact_rule(monkeypatch):
    commands=[];events=[]
    monkeypatch.setattr(trial.os,'geteuid',lambda:0)
    monkeypatch.setattr(trial,'check_scope',lambda *args:None)
    monkeypatch.setattr(trial,'reply_route',lambda *args:'synthetic-wifi')
    monkeypatch.setattr(trial,'read',lambda *args:[])
    monkeypatch.setattr(trial,'emit',events.append)
    monkeypatch.setattr(trial.signal,'signal',lambda *args:None)
    def run(command,**kwargs):commands.append(command);return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(trial.subprocess,'run',run)
    def fail(args):raise RuntimeError('synthetic capture failure')
    monkeypatch.setattr(trial.observer,'capture',fail)
    args=types.SimpleNamespace(address='192.0.2.1',network='192.0.2.0/24',interface='synthetic-wifi')
    with pytest.raises(RuntimeError):trial.route_capture(args)
    assert [command[2] for command in commands]==['add','del']
    assert commands[0][3:]==commands[1][3:]
    assert events[-1]=={'event':'temporary_rule_removed','delete_completed':True,'test_priority_absent':True}


def test_occupied_priority_stops_before_any_change(monkeypatch):
    monkeypatch.setattr(trial,'read',lambda *args:[{'priority':5100}])
    with pytest.raises(ValueError,match='occupied'):
        trial.check_scope('synthetic-wifi','192.0.2.1','192.0.2.0/24')


def test_expired_or_unconfirmed_seed_cannot_start_route_test():
    import datetime as dt
    start=dt.datetime(2026,10,17,21,0,tzinfo=dt.timezone.utc)
    value={'provision_ack':True,'provision_utc':start.isoformat()}
    assert trial.seed_is_recent(value,start+dt.timedelta(seconds=100),120)
    assert not trial.seed_is_recent(value,start+dt.timedelta(seconds=3480),120)
    assert not trial.seed_is_recent(value,start-dt.timedelta(seconds=1),120)
    assert not trial.seed_is_recent(dict(value,provision_ack=False),start,120)
