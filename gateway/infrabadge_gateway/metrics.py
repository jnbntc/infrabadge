"""Strict ingress contract and server-owned health policy (no host identifiers)."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import DeviceId, Epoch, Strict

Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Bytes = Annotated[int, Field(ge=0, le=2**60)]


class Cpu(Strict):
    usage_percent: Percent | None
    logical_cpus: Annotated[int, Field(ge=1, le=8192)]
    load_average: Annotated[list[Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)]],
                            Field(min_length=3, max_length=3)] | None


class Memory(Strict):
    total_bytes: Annotated[int, Field(gt=0, le=2**60)]
    available_bytes: Bytes
    used_bytes: Bytes
    used_percent: Percent
    available_estimated: bool

    @model_validator(mode='after')
    def consistent(self):
        if (self.available_bytes + self.used_bytes != self.total_bytes
                or abs(self.used_percent - 100 * self.used_bytes / self.total_bytes) > 0.011):
            raise ValueError('inconsistent memory')
        return self


class Disk(Strict):
    mount_id: Annotated[str, Field(pattern=r'^[A-Z0-9_-]{1,12}$')]
    total_bytes: Annotated[int, Field(gt=0, le=2**60)]
    available_bytes: Bytes
    used_percent: Percent

    @model_validator(mode='after')
    def consistent(self):
        if (self.available_bytes > self.total_bytes
                or abs(self.used_percent - 100 * (1 - self.available_bytes / self.total_bytes)) > 0.011):
            raise ValueError('inconsistent disk')
        return self


class Temperature(Strict):
    celsius: Annotated[float, Field(ge=-40, le=150, allow_inf_nan=False)]
    sensor: Literal['cpu_package', 'cpu_core', 'cpu_die']


class Metrics(Strict):
    schema_version: Annotated[int, Field(ge=1, le=1)]
    node_id: DeviceId
    collector_version: Annotated[str, Field(pattern=r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$')]
    collected_at: Epoch
    cpu: Cpu | None
    memory: Memory | None
    disk: Disk | None
    temperature: Temperature | None
    uptime_seconds: Annotated[float, Field(ge=0, le=1e12, allow_inf_nan=False)] | None
    errors: Annotated[list[Literal['cpu_unavailable', 'load_unavailable', 'cpu_warmup',
                                  'memory_unavailable', 'disk_unavailable',
                                  'temperature_unavailable', 'uptime_unavailable']], Field(max_length=7)]

    @model_validator(mode='after')
    def unique_errors(self):
        if len(set(self.errors)) != len(self.errors):
            raise ValueError('duplicate errors')
        return self


class Policy(Strict):
    sample_ttl_seconds: Annotated[int, Field(ge=30, le=3600)] = 180
    max_gap_seconds: Annotated[int, Field(ge=10, le=3600)] = 120
    min_interval_seconds: Annotated[int, Field(ge=1, le=3600)] = 30
    cpu_warning: Percent = 85.0
    cpu_critical: Percent = 95.0
    cpu_samples: Annotated[int, Field(ge=2, le=30)] = 3
    available_warning: Percent = 15.0
    available_critical: Percent = 5.0
    recovery_samples: Annotated[int, Field(ge=2, le=30)] = 2
    cpu_hysteresis: Percent = 5.0
    available_hysteresis: Percent = 3.0
    temperature_warning: Annotated[float, Field(ge=0, le=145, allow_inf_nan=False)] | None = None
    temperature_critical: Annotated[float, Field(gt=0, le=150, allow_inf_nan=False)] | None = None
    temperature_hysteresis: Annotated[float, Field(ge=0, le=20, allow_inf_nan=False)] = 3.0

    @model_validator(mode='after')
    def ordered(self):
        if not (0 < self.cpu_warning < self.cpu_critical <= 100
                and 0 <= self.available_critical < self.available_warning < 100
                and self.cpu_hysteresis < self.cpu_warning
                and self.available_warning + self.available_hysteresis < 100
                and self.min_interval_seconds <= self.max_gap_seconds <= self.sample_ttl_seconds):
            raise ValueError('invalid policy')
        if ((self.temperature_warning is None) != (self.temperature_critical is None)
                or (self.temperature_warning is not None
                    and not self.temperature_hysteresis < self.temperature_warning < self.temperature_critical)):
            raise ValueError('temperature requires explicit ordered thresholds')
        return self


class Collector(Strict):
    token_sha256: Annotated[list[Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]], Field(min_length=1, max_length=2)]
    display_name: Annotated[str, Field(pattern=r'^[A-Z0-9_-]{1,12}$')]
    policy: Policy = Field(default_factory=Policy)


class Latch:
    def __init__(self):
        self.active = False
        self.trip = self.clear = 0

    def update(self, bad, recovered, trip_samples, recovery_samples):
        if self.active:
            self.clear = self.clear + 1 if recovered else 0
            if self.clear >= recovery_samples:
                self.active, self.clear, self.trip = False, 0, 0
        else:
            self.trip = self.trip + 1 if bad else 0
            if self.trip >= trip_samples:
                self.active, self.trip = True, 0
        return self.active


class Evaluation:
    def __init__(self):
        self.last = None
        self.latches = {}
        self.status = 'UNKNOWN'

    def ingest(self, sample, policy):
        if (self.last is None or sample.collected_at - self.last.collected_at > policy.max_gap_seconds
                or (sample.uptime_seconds is not None and self.last.uptime_seconds is not None
                    and sample.uptime_seconds <= self.last.uptime_seconds)):
            self.latches.clear()
        critical = warning = False
        missing = (sample.cpu is None or sample.cpu.usage_percent is None
                   or sample.cpu.load_average is None or sample.memory is None
                   or sample.disk is None or sample.uptime_seconds is None)
        values = [('cpu', sample.cpu.usage_percent if sample.cpu else None,
                   policy.cpu_warning, policy.cpu_critical, policy.cpu_hysteresis, policy.cpu_samples)]
        for name in ('memory', 'disk'):
            metric = getattr(sample, name)
            values.append((name, 100 * metric.available_bytes / metric.total_bytes if metric else None,
                           policy.available_warning, policy.available_critical, policy.available_hysteresis, 1))
        if policy.temperature_warning is not None:
            missing |= sample.temperature is None
            values.append(('temperature', sample.temperature.celsius if sample.temperature else None,
                           policy.temperature_warning, policy.temperature_critical, policy.temperature_hysteresis, 1))
        for name, value, warn, crit, hysteresis, trips in values:
            # Missing observations cannot confirm or perpetuate a known alarm.
            if value is None:
                self.latches.pop((name, 'warning'), None)
                self.latches.pop((name, 'critical'), None)
                continue
            low = name in ('memory', 'disk')
            for severity, threshold in [('warning', warn), ('critical', crit)]:
                bad = value <= threshold if low else value >= threshold
                recovered = value > threshold + hysteresis if low else value < threshold - hysteresis
                latch = self.latches.setdefault((name, severity), Latch())
                active = latch.update(bad, recovered, trips, policy.recovery_samples)
                if severity == 'critical':
                    critical |= active
                else:
                    warning |= active
        self.status = 'CRITICAL' if critical else 'WARNING' if warning else 'UNKNOWN' if missing else 'HEALTHY'
        self.last = sample

    def snapshot(self, device_id, collector, now, revision):
        from datetime import datetime, timezone
        from .models import Alert, Counts, Snapshot
        sample, policy = self.last, collector.policy
        fresh = sample is not None and 0 <= now - sample.collected_at < policy.sample_ttl_seconds
        state = self.status if fresh else 'UNKNOWN'
        counts = dict(healthy=0, warning=0, critical=0, unknown=0)
        counts[{'HEALTHY': 'healthy', 'WARNING': 'warning', 'CRITICAL': 'critical'}.get(state, 'unknown')] = 1
        if fresh:
            def percent(metric, attribute):
                value = getattr(metric, attribute) if metric else None
                return '--' if value is None else f'{value:.0f}'
            metrics = f'CPU {percent(sample.cpu, "usage_percent")}% RAM {percent(sample.memory, "used_percent")}% DSK {percent(sample.disk, "used_percent")}%'
            temp = f'{sample.temperature.celsius:.1f} C' if sample.temperature else 'UNKNOWN'
            utc = datetime.fromtimestamp(sample.collected_at, timezone.utc).strftime('%H:%M:%SZ')
            alerts = [Alert(title='NODO ' + collector.display_name, detail=metrics),
                      Alert(title='TEMP CPU ' + temp, detail='MUESTRA ' + utc)]
            generated, expires = sample.collected_at, sample.collected_at + policy.sample_ttl_seconds
        else:
            alerts = [Alert(title='NODO ' + collector.display_name,
                            detail='DATOS CADUCADOS' if sample else 'SIN MUESTRA'),
                      Alert(title='COLLECTOR NO ACTUALIZADO', detail='METRICAS NO VIGENTES')]
            generated, expires = now, now + policy.sample_ttl_seconds
        return Snapshot(schema_version=1, device_id=device_id, revision=revision, simulated=False,
                        generated_at=generated, expires_at=expires, status=state,
                        counts=Counts(**counts), alerts=alerts)
