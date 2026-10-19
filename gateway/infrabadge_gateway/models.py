from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import DeviceId, Epoch, Strict
from .metrics import Collector

State = Literal["HEALTHY", "WARNING", "CRITICAL", "OFFLINE", "UNKNOWN"]
Count = Annotated[int, Field(ge=0, le=999)]


class Counts(Strict):
    healthy: Count
    warning: Count
    critical: Count
    unknown: Count


class Alert(Strict):
    title: Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[A-Z0-9 .:/_%+\-]+$")]
    detail: Annotated[str, Field(min_length=1, max_length=28, pattern=r"^[A-Z0-9 .:/_%+\-]+$")]


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

    @model_validator(mode="after")
    def consistency(self):
        c = self.counts
        if not 0 < c.healthy + c.warning + c.critical + c.unknown <= 999:
            raise ValueError("invalid total")
        state = (
            "CRITICAL"
            if c.critical
            else "WARNING"
            if c.warning
            else "OFFLINE"
            if c.unknown
            else "HEALTHY"
        )
        if self.status not in (("OFFLINE", "UNKNOWN") if state == "OFFLINE" else (state,)):
            raise ValueError("state/count mismatch")
        if not 0 < self.expires_at - self.generated_at <= 3600:
            raise ValueError("invalid validity window")
        return self


class Device(Strict):
    node_id: DeviceId | None = None
    token_sha256: Annotated[list[str], Field(min_length=1, max_length=2)]
    scenario: State = "HEALTHY"
    fault: Literal["json", "oversize", "expired", "version", "auth", "http"] | None = None

    @model_validator(mode="after")
    def hashes(self):
        import re

        if any(not re.fullmatch("[0-9a-f]{64}", value) for value in self.token_sha256):
            raise ValueError("invalid token digest")
        return self


class GatewayConfig(Strict):
    devices: dict[DeviceId, Device]
    enable_faults: bool = False
    collectors: dict[DeviceId, Collector] = Field(default_factory=dict)

    @model_validator(mode="after")
    def identities(self):
        credentials = []
        for device in self.devices.values():
            if device.node_id is not None and (
                device.node_id not in self.collectors or device.fault is not None
            ):
                raise ValueError("real device requires configured collector and no fault injection")
            credentials.extend(device.token_sha256)
        for collector in self.collectors.values():
            credentials.extend(collector.token_sha256)
        if len(set(credentials)) != len(credentials):
            raise ValueError("credentials must be unique across identities and roles")
        return self
