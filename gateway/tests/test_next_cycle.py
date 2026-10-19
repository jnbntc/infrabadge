"""Autonomous observation classification: synthetic metadata only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
import observe_next_cycle as trial


def test_host304_never_becomes_board_evidence():
    value=trial.classify([{'peer_scope':'host','http_status':304,'conditional_request':True}])
    assert not value['external_http_observed']
    assert not value['conditional_304_observed_at_gateway']


def test_external_conditional304_does_not_prove_timer_or_display():
    value=trial.classify([{'peer_scope':'external_unattributed','http_status':304,'conditional_request':True}])
    assert value['conditional_304_observed_at_gateway']
    assert not value['timer_cause_confirmed']
    assert not value['reset_wake_cause_observed']
    assert not value['framebuffer_cancellation_confirmed']
    assert not value['full_m2_validation']


def test_200_or_unconditional304_do_not_meet_conditional304_criterion():
    for status,conditional in [(200,True),(304,False)]:
        assert not trial.classify([{'peer_scope':'external_unattributed','http_status':status,'conditional_request':conditional}])['conditional_304_observed_at_gateway']
