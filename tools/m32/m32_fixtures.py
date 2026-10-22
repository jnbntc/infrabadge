"""Synthetic CI-only topology, never a real host inventory."""

import hashlib

from infrabadge_gateway.distributed.config import CoreConfig
from infrabadge_gateway.metrics import Metrics

NOW = 1800000000

TOKENS = {
    key: key[0] * 40
    for key in (
        "collector-a",
        "d-device",
        "e-edge",
        "r-reader",
        "b-collector",
        "s-reader",
        "f-device",
        "g-edge",
    )
}


def identity(key, **fields):
    return dict(token_sha256=[hashlib.sha256(TOKENS[key].encode()).hexdigest()], **fields)


def configuration(**changes):
    raw = dict(
        sites=dict(alpha=dict(display_name="ALPHA"), beta=dict(display_name="BETA")),
        nodes=dict(
            a=dict(site_id="alpha", display_name="NODE_A", node_type="linux", enabled=True),
            b=dict(site_id="beta", display_name="NODE_B", node_type="mobile", enabled=True),
        ),
        collectors={"a": identity("collector-a"), "b": identity("b-collector")},
        devices={
            "display-a": identity("d-device", site_ids=["alpha"]),
            "display-b": identity("f-device", site_ids=["beta"]),
        },
        readers={
            "read-a": identity("r-reader", site_ids=["alpha"]),
            "read-b": identity("s-reader", site_ids=["beta"]),
        },
        edges={
            "edge-a": identity("e-edge", device_ids=["display-a"]),
            "edge-b": identity("g-edge", device_ids=["display-b"]),
        },
    )
    raw.update(changes)
    return CoreConfig.model_validate(raw)


def sample(node="a", at=NOW, cpu=20.0, available=70):
    return Metrics.model_validate(
        dict(
            schema_version=1,
            node_id=node,
            collector_version="0.3.0",
            collected_at=at,
            cpu=dict(usage_percent=float(cpu), logical_cpus=4, load_average=[0.1, 0.2, 0.3]),
            memory=dict(
                total_bytes=10000,
                available_bytes=available * 100,
                used_bytes=10000 - available * 100,
                used_percent=float(100 - available),
                available_estimated=False,
            ),
            disk=dict(mount_id="ROOT", total_bytes=10000, available_bytes=6000, used_percent=40.0),
            temperature=None,
            uptime_seconds=float(1000 + at - NOW),
            errors=["temperature_unavailable"],
        )
    )


def headers(key, edge=None, **extra):
    return (
        {"Authorization": "Bearer " + TOKENS[key]}
        | ({"X-InfraBadge-Edge": "Bearer " + TOKENS[edge]} if edge else {})
        | extra
    )
