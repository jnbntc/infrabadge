import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from infrabadge_gateway.app import create_app
from infrabadge_gateway.metrics import Policy
from infrabadge_gateway.models import GatewayConfig, Snapshot

NOW = 1800000000
DEVICE_TOKEN = 'd' * 40
COLLECTOR_TOKEN = 'c' * 40


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def configuration():
    return GatewayConfig.model_validate({
        'devices': {'badge': {'node_id': 'workstation', 'token_sha256': [digest(DEVICE_TOKEN)]}},
        'collectors': {'workstation': {'display_name': 'WORKSTATION', 'token_sha256': [digest(COLLECTOR_TOKEN)]}}})


def sample(at=NOW, cpu=20.0, available=70, disk_available=60):
    return dict(schema_version=1, node_id='workstation', collector_version='0.3.0', collected_at=at,
                cpu=dict(usage_percent=cpu, logical_cpus=8, load_average=[1.0, 2.0, 3.0]),
                memory=dict(total_bytes=10000, available_bytes=available * 100,
                            used_bytes=(100 - available) * 100, used_percent=float(100 - available),
                            available_estimated=False),
                disk=dict(mount_id='HOME', total_bytes=10000, available_bytes=disk_available * 100,
                          used_percent=float(100 - disk_available)),
                temperature=None, uptime_seconds=float(1000 + at - NOW), errors=['temperature_unavailable'])


class Lab:
    def __init__(self, config=None):
        self.now = NOW
        self.config = config or configuration()
        self.client = TestClient(create_app(self.config, clock=lambda: self.now))

    def post(self, value=None, token=COLLECTOR_TOKEN, **kwargs):
        return self.client.post('/api/v1/collectors/workstation/metrics', json=value or sample(self.now),
                                headers={'Authorization': 'Bearer ' + token}, **kwargs)

    def get(self, etag=None, token=DEVICE_TOKEN):
        headers = {'Authorization': 'Bearer ' + token}
        if etag:
            headers['If-None-Match'] = etag
        return self.client.get('/api/v1/devices/badge/status', headers=headers)


def test_separate_roles_missing_and_valid_sample():
    lab = Lab()
    assert lab.get().json()['status'] == 'UNKNOWN'
    assert lab.post(token=DEVICE_TOKEN).status_code == 401
    assert lab.get(token=COLLECTOR_TOKEN).status_code == 401
    assert lab.post().status_code == 202
    result = lab.get()
    snapshot = Snapshot.model_validate(result.json())
    assert snapshot.status == 'HEALTHY' and snapshot.simulated is False
    assert snapshot.expires_at == NOW + 180
    assert 'WORKSTATION' in snapshot.alerts[0].title
    assert 'DSK 40%' in snapshot.alerts[0].detail
    assert snapshot.alerts[1].title == 'TEMP CPU UNKNOWN'
    assert len(result.content) <= 2048


def test_duplicate_out_of_order_future_and_expired_do_not_replace_last_valid():
    lab = Lab()
    assert lab.post().status_code == 202
    for at, code in [(NOW, 409), (NOW - 1, 409), (NOW + 1, 422), (NOW - 180, 422)]:
        assert lab.post(sample(at)).status_code == code
    assert lab.get().json()['status'] == 'HEALTHY'


def test_etag_ttl_stale_recovery_and_clock_rollback():
    lab = Lab()
    lab.post()
    initial = lab.get()
    tag = initial.headers['etag']
    lab.now += 100
    same = lab.get(tag)
    assert same.status_code == 304 and same.content == b''
    lab.now = NOW + 180
    stale = lab.get(tag)
    assert stale.status_code == 200 and stale.json()['status'] == 'UNKNOWN'
    assert stale.json()['alerts'][0]['detail'] == 'DATOS CADUCADOS'
    assert lab.get(stale.headers['etag']).status_code == 304
    lab.post(sample(lab.now - 20))
    assert lab.get(stale.headers['etag']).json()['status'] == 'HEALTHY'
    assert lab.get().json()['expires_at'] == lab.now - 20 + 180
    lab.now -= 21
    assert lab.get().json()['status'] == 'UNKNOWN'


@pytest.mark.parametrize('change', [
    {'node_id': 'another'}, {'schema_version': True}, {'status': 'CRITICAL'},
    {'cpu': {'usage_percent': 101.0, 'logical_cpus': 8, 'load_average': [1.0] * 3}},
    {'temperature': {'celsius': 50.0, 'sensor': 'unknown_cpu'}},
    {'errors': ['private path']}, {'uptime_seconds': -1.0}, {'collector_version': 'bad'},
    {'memory': {'total_bytes': 100, 'available_bytes': 90, 'used_bytes': 20,
                'used_percent': 20.0, 'available_estimated': False}},
    {'disk': {'mount_id': '/var/home/private', 'total_bytes': 100, 'available_bytes': 200, 'used_percent': 20.0}},
])
def test_strict_payload_and_no_echo(change):
    lab = Lab()
    payload = sample()
    payload.update(change)
    result = lab.post(payload)
    assert result.status_code == 422
    assert result.json()['detail'] in ('metrics rejected', 'metrics identity or freshness rejected')


@pytest.mark.parametrize('body,code', [('{broken', 422), ('{"schema_version":1,"schema_version":1}', 422),
                                     ('{"cpu":NaN}', 422), ('[' * 2000, 422), ('x' * 8193, 413)])
def test_bounded_json(body, code):
    lab = Lab()
    response = lab.client.post('/api/v1/collectors/workstation/metrics', content=body,
                               headers={'Authorization': 'Bearer ' + COLLECTOR_TOKEN, 'Content-Type': 'application/json'})
    assert response.status_code == code


def test_auth_before_body_and_encodings():
    lab = Lab()
    endpoint = '/api/v1/collectors/workstation/metrics'
    assert lab.client.post(endpoint, content='x' * 10000).status_code == 401
    assert lab.client.post(endpoint, content='x', headers={'Authorization': 'Bearer ' + COLLECTOR_TOKEN}).status_code == 415
    assert lab.client.post(endpoint, json=sample(), headers={'Authorization': 'Bearer ' + COLLECTOR_TOKEN,
                                                          'Content-Encoding': 'gzip'}).status_code == 415


def test_cpu_sustained_recovery_hysteresis_and_gap():
    lab = Lab()
    for cpu, expected in [(97, 'HEALTHY'), (97, 'HEALTHY'), (97, 'CRITICAL'),
                          (93, 'CRITICAL'), (79, 'CRITICAL'), (79, 'HEALTHY'),
                          (86, 'HEALTHY'), (96, 'HEALTHY'), (86, 'WARNING')]:
        assert lab.post(sample(lab.now, float(cpu))).status_code == 202
        assert lab.get().json()['status'] == expected
        lab.now += 60
    lab.now += 121
    lab.post(sample(lab.now, 99.0))
    assert lab.get().json()['status'] == 'HEALTHY'


def test_memory_disk_precedence_recovery_missing_and_restart():
    lab = Lab()
    lab.post(sample(available=15, disk_available=5))
    assert lab.get().json()['status'] == 'CRITICAL'
    lab.now += 60
    missing = sample(lab.now)
    missing['disk'] = None
    missing['memory'] = None
    lab.post(missing)
    assert lab.get().json()['status'] == 'UNKNOWN'
    lab.now += 60
    lab.post(sample(lab.now, available=10))
    assert lab.get().json()['status'] == 'WARNING'
    for available, expected in [(17, 'WARNING'), (30, 'WARNING'), (30, 'HEALTHY')]:
        lab.now += 60
        lab.post(sample(lab.now, available=available))
        assert lab.get().json()['status'] == expected
    assert Lab().get().json()['status'] == 'UNKNOWN'  # process restart has no persisted live data


def test_temperature_opt_in_and_missing_cpu():
    config = configuration()
    config.collectors['workstation'].policy = Policy(temperature_warning=70.0, temperature_critical=90.0)
    lab = Lab(config)
    lab.post()
    assert lab.get().json()['status'] == 'UNKNOWN'
    payload = sample(NOW + 60)
    payload['temperature'] = dict(celsius=95.0, sensor='cpu_die')
    payload['cpu']['usage_percent'] = None
    lab.now += 60
    lab.post(payload)
    assert lab.get().json()['status'] == 'CRITICAL'


def test_identity_isolation_configuration_and_faults():
    config = configuration().model_dump()
    reused = copy.deepcopy(config)
    reused['collectors']['workstation']['token_sha256'] = [digest(DEVICE_TOKEN)]
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate(reused)
    config['enable_faults'] = True
    config['collectors']['other'] = dict(display_name='OTHER', token_sha256=[digest('o' * 40)])
    config['devices']['otherbadge'] = dict(node_id='other', token_sha256=[digest('b' * 40)])
    lab = Lab(GatewayConfig.model_validate(config))
    assert lab.client.post('/api/v1/collectors/other/metrics', json=sample(),
                           headers={'Authorization': 'Bearer ' + COLLECTOR_TOKEN}).status_code == 401
    assert lab.client.get('/api/v1/devices/badge/status?fault=json',
                          headers={'Authorization': 'Bearer ' + DEVICE_TOKEN}).status_code == 404
    lab.post()
    assert lab.client.get('/api/v1/devices/otherbadge/status',
                          headers={'Authorization': 'Bearer ' + 'b' * 40}).json()['status'] == 'UNKNOWN'


@pytest.mark.parametrize('options', [{'cpu_warning': 95.0, 'cpu_critical': 85.0},
                                    {'temperature_warning': 80.0}, {'max_gap_seconds': 500},
                                    {'cpu_samples': 1}, {'available_critical': 20.0}])
def test_policy_rejects_unsafe_or_inconsistent_values(options):
    with pytest.raises(ValidationError):
        Policy(**options)
