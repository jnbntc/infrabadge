"""Deterministic proc/sys fixtures -> actual collector TLS -> gateway M2 contract."""

import ssl
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/m3"))
from infrabadge_collector.acquire import acquire
from infrabadge_collector.transport import submit
from infrabadge_gateway.models import Snapshot
from lab_support import loopback


def fixture_metrics(folder, monkeypatch):
    folder.mkdir()
    (folder / "uptime").write_text("1000.0 0")
    (folder / "stat").write_text("cpu 100 0 0 200 0 0 0 0\ncpu0 1\n")
    (folder / "loadavg").write_text("0.5 1.0 1.5 1/2 3")
    (folder / "meminfo").write_text("MemTotal: 10000 kB\nMemAvailable: 6000 kB\n")
    # No physical sensor dependency in CI.
    monkeypatch.setattr("infrabadge_collector.acquire.cpu_temperature", lambda _: None)
    monkeypatch.setattr(
        "infrabadge_collector.acquire.disk_usage",
        lambda _path, _label: dict(
            mount_id="HOME", total_bytes=10000, available_bytes=6000, used_percent=40.0
        ),
    )
    _, previous = acquire("workstation", folder, "HOME", proc_root=folder, now=1800000000)
    (folder / "uptime").write_text("1060.0 0")
    (folder / "stat").write_text("cpu 120 0 0 280 0 0 0 0\ncpu0 1\n")
    return acquire("workstation", folder, "HOME", previous, proc_root=folder, now=1800000000)[0]


@pytest.mark.parametrize("kind", ["valid", "expired", "wronghost"])
def test_collector_real_verified_tls(tmp_path, monkeypatch, kind):
    metrics = fixture_metrics(tmp_path / "proc", monkeypatch)
    with loopback(tmp_path, clock=lambda: 1800000000, certificate_kind=kind) as (
        config,
        token,
        device,
    ):
        if kind != "valid":
            with pytest.raises(ssl.SSLCertVerificationError):
                submit(config, token, metrics)
            return
        submit(config, token, metrics)
        with httpx.Client(
            verify=ssl.create_default_context(cafile=config["ca_file"]), trust_env=False
        ) as client:
            headers = {"Authorization": "Bearer " + device}
            response = client.get(
                config["gateway_url"] + "/api/v1/devices/badge-lab/status", headers=headers
            )
            snapshot = Snapshot.model_validate(response.json())
            assert not snapshot.simulated and snapshot.status == "HEALTHY"
            assert snapshot.expires_at == metrics["collected_at"] + 180
            assert "CPU 20%" in snapshot.alerts[0].detail
            assert (
                client.get(
                    config["gateway_url"] + "/api/v1/devices/badge-lab/status",
                    headers={**headers, "If-None-Match": response.headers["etag"]},
                ).status_code
                == 304
            )
        assert submit_rejected(config, token, metrics)  # duplicate is rejected, never retried
        token.write_text("a" * 40)
        assert submit_rejected(config, token, metrics)


def submit_rejected(config, token, metrics):
    with pytest.raises(ValueError, match="gateway_rejected"):
        submit(config, token, metrics)
    return True
