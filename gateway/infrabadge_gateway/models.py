from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

DeviceId = Annotated[str, Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,31}$')]
State = Literal['HEALTHY', 'WARNING', 'CRITICAL', 'OFFLINE', 'UNKNOWN']
Epoch = Annotated[int, Field(ge=1577836800, le=4102444800)]
Count = Annotated[int, Field(ge=0, le=999)]

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Counts(Strict):
    healthy: Count
    warning: Count
    critical: Count
    unknown: Count

class Alert(Strict):
    title: Annotated[str, Field(min_length=1, max_length=24, pattern=r'^[A-Z0-9 .:/_%+\-]+$')]
    detail: Annotated[str, Field(min_length=1, max_length=28, pattern=r'^[A-Z0-9 .:/_%+\-]+$')]

class Snapshot(Strict):
    schema_version: Annotated[int, Field(ge=1, le=1)]
    device_id: DeviceId
    revision: Annotated[int, Field(ge=1, le=2147483647)]
    simulated: bool
    generated_at: Epoch
    expires_at: Epoch
    status: State
    counts: Counts
    alerts: Annotated[list[Alert], Field(max_length=2)]

    @model_validator(mode='after')
    def consistency(self):
        if self.simulated is not True:
            raise ValueError('M2 only accepts simulated data')
        c = self.counts
        if not 0 < c.healthy + c.warning + c.critical + c.unknown <= 999:
            raise ValueError('invalid total')
        state = 'CRITICAL' if c.critical else 'WARNING' if c.warning else 'OFFLINE' if c.unknown else 'HEALTHY'
        if self.status not in (('OFFLINE', 'UNKNOWN') if state == 'OFFLINE' else (state,)):
            raise ValueError('state/count mismatch')
        if not 0 < self.expires_at - self.generated_at <= 3600:
            raise ValueError('invalid validity window')
        return self

class Device(Strict):
    token_sha256: Annotated[list[str], Field(min_length=1, max_length=2)]
    scenario: State = 'HEALTHY'
    fault: Literal['json','oversize','expired','version','auth','http'] | None = None

    @model_validator(mode='after')
    def hashes(self):
        import re
        if any(not re.fullmatch('[0-9a-f]{64}', value) for value in self.token_sha256):
            raise ValueError('invalid token digest')
        return self

class GatewayConfig(Strict):
    devices: dict[DeviceId, Device]
    enable_faults: bool = False
