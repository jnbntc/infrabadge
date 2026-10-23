"""Private, server-owned multisite inventory. No addresses or discovery."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..base import DeviceId, Epoch, Strict
from ..metrics import Metrics, Policy
from ..models import State

Hashes = Annotated[
    list[Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]], Field(min_length=1, max_length=2)
]
Ids = Annotated[list[DeviceId], Field(min_length=1, max_length=16)]


class Identity(Strict):
    token_sha256: Hashes


class Site(Strict):
    display_name: Annotated[str, Field(pattern=r"^[A-Z0-9_-]{1,12}$")]
    enabled: bool = True


class Node(Strict):
    site_id: DeviceId
    display_name: Annotated[str, Field(pattern=r"^[A-Z0-9_-]{1,12}$")]
    node_type: Literal["linux", "gateway", "mobile"]
    enabled: bool = False
    health_policy: Policy = Field(default_factory=Policy)
    offline_after_seconds: Annotated[int, Field(ge=30, le=86400)] = 600

    @model_validator(mode="after")
    def offline_after_ttl(self):
        if self.offline_after_seconds < self.health_policy.sample_ttl_seconds:
            raise ValueError("offline horizon precedes TTL")
        return self


class ViewIdentity(Identity):
    site_ids: Ids


class DisplayIdentity(ViewIdentity):
    presentation_v2: bool = False


class EdgeIdentity(Identity):
    device_ids: Ids


class CoreConfig(Strict):
    schema_version: Literal[1] = 1
    sites: Annotated[dict[DeviceId, Site], Field(min_length=1, max_length=16)]
    nodes: Annotated[dict[DeviceId, Node], Field(max_length=64)]
    collectors: Annotated[dict[DeviceId, Identity], Field(max_length=64)] = Field(
        default_factory=dict
    )
    devices: Annotated[dict[DeviceId, DisplayIdentity], Field(max_length=16)] = Field(
        default_factory=dict
    )
    readers: Annotated[dict[DeviceId, ViewIdentity], Field(max_length=16)] = Field(
        default_factory=dict
    )
    edges: Annotated[dict[DeviceId, EdgeIdentity], Field(max_length=16)] = Field(
        default_factory=dict
    )
    require_edge: bool = True
    history_per_node: Annotated[int, Field(ge=1, le=240)] = 60
    history_seconds: Annotated[int, Field(ge=60, le=604800)] = 86400
    control_ttl_seconds: Annotated[int, Field(ge=10, le=60)] = 30

    @model_validator(mode="after")
    def scope(self):
        if any(n.site_id not in self.sites for n in self.nodes.values()):
            raise ValueError("unknown site")
        if any(n not in self.nodes for n in self.collectors):
            raise ValueError("collector requires node")
        credentials = []
        for group in (self.collectors, self.devices, self.readers, self.edges):
            for identity in group.values():
                credentials.extend(identity.token_sha256)
                scope = getattr(identity, "site_ids", getattr(identity, "device_ids", []))
                allowed = self.devices if isinstance(identity, EdgeIdentity) else self.sites
                if len(set(scope)) != len(scope) or any(s not in allowed for s in scope):
                    raise ValueError("invalid identity scope")
        if len(set(credentials)) != len(credentials):
            raise ValueError("credentials must be unique across identities and roles")
        return self


class NodeView(Strict):
    site_id: DeviceId
    node_id: DeviceId
    node_type: Literal["linux", "gateway", "mobile"]
    enabled: bool
    last_seen: Epoch | None
    status: State
    metrics: Metrics | None
    historical_metrics: Metrics | None
    freshness: Literal["disabled", "never", "fresh", "restored", "stale"]
    age_seconds: Annotated[int, Field(ge=0)] | None
    health_policy: Policy

    @model_validator(mode="after")
    def current_is_explicit(self):
        if (self.freshness == "fresh") != (self.metrics is not None):
            raise ValueError("fresh metrics required only for current samples")
        if self.metrics is not None and self.historical_metrics is not None:
            raise ValueError("historical data cannot be current")
        return self


class SiteView(Strict):
    site_id: DeviceId
    status: State
    nodes: Annotated[list[NodeView], Field(max_length=64)]
