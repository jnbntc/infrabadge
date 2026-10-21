"""Synthetic inputs for CI, never notebook inventory or real credentials."""

import hashlib

from infrabadge_gateway.lan_policy import LanPolicy
from infrabadge_gateway.models import GatewayConfig

NOW = 1800000000
DEVICE = "d" * 40
COLLECTOR = "c" * 40


def policy(**changes):
    fields = dict(
        interface="wifi-test",
        address="10.23.42.10",
        network="10.23.42.0/24",
        connection_uuid="12345678-1234-4234-8234-123456789abc",
        ssid_sha256=hashlib.sha256(b"SYNTHETIC LAB").hexdigest(),
        firewall_zone="lab",
        firewall_sha256=hashlib.sha256(b"reviewed synthetic rules").hexdigest(),
        hostname="badge-gateway.test",
        image="sha256:" + "a" * 64,
        devices=["badge"],
    )
    return LanPolicy(**(fields | changes))


def configuration():
    return GatewayConfig.model_validate(
        dict(
            devices=dict(
                badge=dict(
                    node_id="workstation",
                    token_sha256=[hashlib.sha256(DEVICE.encode()).hexdigest()],
                )
            ),
            collectors=dict(
                workstation=dict(
                    display_name="WORKSTATION",
                    token_sha256=[hashlib.sha256(COLLECTOR.encode()).hexdigest()],
                )
            ),
        )
    )


def sample(at=NOW):
    return dict(
        schema_version=1,
        node_id="workstation",
        collector_version="0.3.0",
        collected_at=at,
        cpu=dict(usage_percent=20.0, logical_cpus=4, load_average=[0.1, 0.2, 0.3]),
        memory=dict(
            total_bytes=10000,
            available_bytes=7000,
            used_bytes=3000,
            used_percent=30.0,
            available_estimated=False,
        ),
        disk=dict(mount_id="HOME", total_bytes=10000, available_bytes=6000, used_percent=40.0),
        temperature=None,
        uptime_seconds=float(1000 + at - NOW),
        errors=["temperature_unavailable"],
    )
