import hashlib
import hmac
import json
import threading
import time
from collections.abc import Callable
from typing import Annotated
from fastapi import FastAPI, Header, HTTPException, Path, Query, Response
from .models import Alert, Counts, GatewayConfig, Snapshot

def fixture(device_id: str, state: str, now: int, revision: int, ttl_seconds: int = 1800) -> Snapshot:
    counts = {'healthy': 12, 'warning': 0, 'critical': 0, 'unknown': 0}
    alerts = []
    if state == 'WARNING':
        counts.update(healthy=11, warning=1)
        alerts = [Alert(title='CPU ALTA', detail='NODO-02 / CPU 84%')]
    elif state == 'CRITICAL':
        counts.update(healthy=10, critical=2)
        alerts = [Alert(title='SERVICIO CAIDO', detail='NODO-03 / API'),
                  Alert(title='DISCO LLENO', detail='NODO-07 / USO 99%')]
    elif state in ('OFFLINE', 'UNKNOWN'):
        counts.update(healthy=0, unknown=12)
        alerts = [Alert(title='SIN DATOS', detail='ESTADO DESCONOCIDO')]
    return Snapshot(schema_version=1, device_id=device_id, revision=revision, simulated=True,
                    generated_at=now, expires_at=now+ttl_seconds, status=state,
                    counts=Counts(**counts), alerts=alerts)

def create_app(config: GatewayConfig, clock: Callable[[], float] = time.time,
               snapshot_ttl_seconds: int = 1800) -> FastAPI:
    if type(snapshot_ttl_seconds) is not int or not 0 < snapshot_ttl_seconds <= 3600:
        raise ValueError('snapshot TTL outside protocol bounds')
    app = FastAPI(title='InfraBadge mock gateway', docs_url=None, redoc_url=None)
    lock = threading.Lock()
    cached: dict[str, Snapshot] = {}

    @app.get('/api/v1/devices/{device_id}/status')
    def status(device_id: Annotated[str, Path(pattern=r'^[a-z0-9][a-z0-9_-]{0,31}$')],
               authorization: Annotated[str | None, Header()] = None,
               if_none_match: Annotated[str | None, Header()] = None,
               fault: Annotated[str | None, Query(max_length=32)] = None):
        device = config.devices.get(device_id)
        token = authorization[7:] if authorization and authorization.startswith('Bearer ') else ''
        digest = hashlib.sha256(token.encode()).hexdigest()
        accepted = False
        for value in device.token_sha256 if device else ['0'*64]:
            accepted |= hmac.compare_digest(digest, value)
        if not device or not 32 <= len(token) <= 96 or not accepted:
            raise HTTPException(401, 'device authentication rejected', headers={'WWW-Authenticate': 'Bearer'})
        now = int(clock())
        headers = {'X-InfraBadge-Now': str(now), 'Cache-Control': 'private, no-cache'}
        fault = fault or device.fault
        if fault:
            if not config.enable_faults:
                raise HTTPException(404, 'fault injection disabled')
            if fault == 'json': return Response('{broken', media_type='application/json', headers=headers)
            if fault == 'oversize': return Response('x'*4096, media_type='application/json', headers=headers)
            if fault == 'auth': raise HTTPException(401, 'simulated rejection')
            if fault == 'http': raise HTTPException(503, 'simulated unavailability')
            if fault not in ('expired','version'): raise HTTPException(404, 'unknown fault')
        with lock:
            old = cached.get(device_id)
            if not old or now >= old.expires_at or old.status != device.scenario:
                old = fixture(device_id, device.scenario, now, old.revision+1 if old else 1,
                              snapshot_ttl_seconds)
                cached[device_id] = old
            data = old.model_dump()
            if fault == 'expired': data.update(generated_at=now-3600, expires_at=now-1)
            if fault == 'version': data['schema_version'] = 99
            body = json.dumps(data, separators=(',', ':'), sort_keys=True).encode('ascii')
            etag = '"'+hashlib.sha256(body).hexdigest()+'"'
        headers['ETag'] = etag
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)
        return Response(body, media_type='application/json', headers=headers)
    return app
