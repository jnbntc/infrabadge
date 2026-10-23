"""Device-scoped v2 projection: bounded current data, never reader inventory/history."""

import hashlib
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..base import DeviceId, Epoch, Strict
from ..models import State
from .core import aggregate, latest, restore_evaluation
from .private import encode

MAX_BYTES = 4096
Percent10 = Annotated[int, Field(ge=0, le=1000)]
Temperature100 = Annotated[int, Field(ge=-4000, le=15000)]
Name = Annotated[str, Field(pattern=r"^[A-Z0-9_-]{1,12}$")]


class Site(Strict):
    id: DeviceId
    name: Name
    status: State


class Node(Strict):
    id: DeviceId
    name: Name
    site: DeviceId
    status: State
    sampled_at: Epoch | None
    valid_until: Epoch | None
    cpu: Percent10 | None
    ram: Percent10 | None
    disk: Percent10 | None
    temperature: Temperature100 | None


class Alert(Strict):
    node: DeviceId
    severity: Literal["CRITICAL", "WARNING"]
    metric: Literal["CPU", "RAM", "DISK", "TEMP"]
    value: Annotated[int, Field(ge=-4000, le=15000)]
    at: Epoch


class Presentation(Strict):
    schema_version: Literal[2]
    device_id: DeviceId
    revision: Annotated[int, Field(ge=1, le=2147483647)]
    generated_at: Epoch
    expires_at: Epoch
    status: State
    sites: Annotated[list[Site], Field(min_length=1, max_length=3)]
    nodes: Annotated[list[Node], Field(max_length=6)]
    alerts: Annotated[list[Alert], Field(max_length=4)]
    more_alerts: Annotated[int, Field(ge=0, le=64)]

    @model_validator(mode="after")
    def coherent(self):
        sites = {s.id for s in self.sites}
        nodes = {n.id: n for n in self.nodes}
        if (
            len(sites) != len(self.sites)
            or len(nodes) != len(self.nodes)
            or not 0 < self.expires_at - self.generated_at <= 3600
            or any(n.site not in sites for n in self.nodes)
            or aggregate([n.status for n in self.nodes]) != self.status
            or any(
                aggregate([n.status for n in self.nodes if n.site == s.id]) != s.status
                for s in self.sites
            )
        ):
            raise ValueError("projection integrity")
        for n in self.nodes:
            if n.sampled_at is not None and n.sampled_at > self.generated_at:
                raise ValueError("future sample")
            if n.valid_until is None:
                if any(
                    v is not None for v in (n.cpu, n.ram, n.disk, n.temperature)
                ) or n.status not in ("UNKNOWN", "OFFLINE"):
                    raise ValueError("historical data cannot be current")
            elif (
                n.sampled_at is None
                or not n.sampled_at <= self.generated_at < self.expires_at <= n.valid_until
                or not 0 < n.valid_until - n.sampled_at <= 3600
            ):
                raise ValueError("sample deadline")
        seen, warning_seen = set(), False
        for a in self.alerts:
            if a.node not in nodes or (a.node, a.metric) in seen:
                raise ValueError("alert identity")
            seen.add((a.node, a.metric))
            n = nodes[a.node]
            key = {"CPU": "cpu", "RAM": "ram", "DISK": "disk", "TEMP": "temperature"}[a.metric]
            if (
                n.valid_until is None
                or n.status not in ("WARNING", "CRITICAL")
                or a.value != getattr(n, key)
                or a.at != n.sampled_at
                or (warning_seen and a.severity == "CRITICAL")
            ):
                raise ValueError("alert sample")
            warning_seen |= a.severity == "WARNING"
        return self


def project(core, device_id, now):
    """One transaction, reused SQLite snapshot cache under a distinct v2 key."""
    identity = core.config.devices[device_id]
    if not identity.presentation_v2:
        raise ValueError("v2 not enabled")
    with core.store.transaction() as db:
        core.checked_clock(db, now)
        views = [
            core.node_view(db, n, now)
            for n, definition in sorted(core.config.nodes.items())
            if definition.site_id in identity.site_ids
            and definition.enabled
            and core.config.sites[definition.site_id].enabled
        ]
        if len(identity.site_ids) > 3 or len(views) > 6:
            raise ValueError("device projection capacity")
        nodes, alerts = [], []
        deadline = now + core.config.control_ttl_seconds
        # Start with the earliest sample deadline when every node is fresh.
        if views and all(v["metrics"] for v in views):
            deadline = now + 3600
        for v in views:
            definition = core.config.nodes[v["node_id"]]
            m = v["metrics"]
            historical = v["historical_metrics"]
            at = (m or historical or {}).get("collected_at")
            valid_until = at + definition.health_policy.sample_ttl_seconds if m else None
            if valid_until:
                deadline = min(deadline, valid_until)
            elif at is not None and now < at + definition.offline_after_seconds:
                deadline = min(deadline, at + definition.offline_after_seconds)
            node = dict(
                id=v["node_id"],
                name=definition.display_name,
                site=v["site_id"],
                status=v["status"],
                sampled_at=at,
                valid_until=valid_until,
                cpu=round(m["cpu"]["usage_percent"] * 10)
                if m and m["cpu"] and m["cpu"]["usage_percent"] is not None
                else None,
                ram=round(m["memory"]["used_percent"] * 10) if m and m["memory"] else None,
                disk=round(m["disk"]["used_percent"] * 10) if m and m["disk"] else None,
                temperature=round(m["temperature"]["celsius"] * 100)
                if m and m["temperature"]
                else None,
            )
            nodes.append(node)
            if m:
                evaluation = restore_evaluation(latest(db, v["node_id"]), core.session)
                for metric, label in (
                    ("cpu", "CPU"),
                    ("memory", "RAM"),
                    ("disk", "DISK"),
                    ("temperature", "TEMP"),
                ):
                    for severity in ("critical", "warning"):
                        latch = evaluation.latches.get((metric, severity))
                        if latch and latch.active:
                            value = node[
                                {"memory": "ram", "temperature": "temperature"}.get(metric, metric)
                            ]
                            if value is not None:
                                alerts.append(
                                    dict(
                                        node=node["id"],
                                        severity=severity.upper(),
                                        metric=label,
                                        value=value,
                                        at=at,
                                    )
                                )
                            break
        alerts.sort(key=lambda a: (a["severity"] != "CRITICAL", a["node"], a["metric"]))
        sites = [
            dict(
                id=s,
                name=core.config.sites[s].display_name,
                status=aggregate([n["status"] for n in nodes if n["site"] == s]),
            )
            for s in sorted(identity.site_ids)
        ]
        data = dict(
            schema_version=2,
            device_id=device_id,
            status=aggregate([n["status"] for n in nodes]),
            sites=sites,
            nodes=nodes,
            alerts=alerts[:4],
            more_alerts=max(0, len(alerts) - 4),
        )
        fingerprint = hashlib.sha256(encode(data).encode()).hexdigest()
        key = "v2:" + device_id
        old = db.execute(
            "SELECT revision,fingerprint,body,session FROM snapshots WHERE device=?", (key,)
        ).fetchone()
        if (
            old
            and old[1] == fingerprint
            and old[3] == core.session
            and now < Presentation.model_validate_json(old[2]).expires_at
        ):
            return old[2].encode()
        revision = old[0] + 1 if old else 1
        model = Presentation.model_validate(
            data | dict(revision=revision, generated_at=now, expires_at=deadline)
        )
        body = encode(model.model_dump())
        if len(body.encode()) > MAX_BYTES:
            raise ValueError("projection bytes")
        db.execute(
            "INSERT INTO snapshots VALUES(?,?,?,?,?) ON CONFLICT(device) DO UPDATE SET revision=excluded.revision,fingerprint=excluded.fingerprint,body=excluded.body,session=excluded.session",
            (key, revision, fingerprint, body, core.session),
        )
        return body.encode()
