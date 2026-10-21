"""M3.1 pure/ASGI tests; synthetic network fixtures, no host services or board."""

import concurrent.futures
import dataclasses
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from infrabadge_gateway import lan_guard
from infrabadge_gateway.app import create_app
from infrabadge_gateway.lan_edge import LanEntrance
from infrabadge_gateway.lan_policy import LanPolicy, lease_valid, write_private
from infrabadge_gateway.lan_telemetry import Telemetry, view
from infrabadge_gateway.models import Snapshot
from m31_fixtures import COLLECTOR, DEVICE, NOW, configuration, policy, sample

ROOT = Path(__file__).resolve().parents[2]


def clients(authorized=lambda: True, p=None, clock=lambda: NOW):
    p = p or policy()
    config = configuration()
    telemetry = Telemetry(clock=clock)
    app = create_app(config, clock=clock, events=telemetry.emit)
    edge = LanEntrance(app, config, p, authorized, telemetry)
    return TestClient(app), TestClient(edge, base_url="https://" + p.hostname + ":8443"), telemetry


def post(client, at=NOW):
    return client.post(
        "/api/v1/collectors/workstation/metrics",
        json=sample(at),
        headers={"Authorization": "Bearer " + COLLECTOR},
    )


def get(client, **kwargs):
    headers = {"Authorization": "Bearer " + DEVICE}
    headers.update(kwargs.pop("headers", {}))
    return client.get("/api/v1/devices/badge/status", headers=headers, **kwargs)


@pytest.mark.parametrize(
    "change",
    [
        dict(address="0.0.0.0"),
        dict(address="127.0.0.1"),
        dict(address="8.8.8.8", network="8.8.8.0/24"),
        dict(address="::1"),
        dict(network="0.0.0.0/0"),
        dict(network="10.23.0.0/8"),
        dict(address="10.23.42.0"),
        dict(interface="x\nPublishPort=0.0.0.0:8443"),
        dict(image="latest"),
        dict(devices=["badge", "badge"]),
        dict(device_per_minute=True),
        dict(hostname="*.example.com"),
        dict(connection_uuid="wrong"),
        dict(schema_version=2),
    ],
)
def test_policy_rejects_broad_invalid_or_injected_configuration(change):
    with pytest.raises((ValueError, TypeError)):
        policy(**change)


def test_shared_state_exact_contract_etag_expiry_and_recovery():
    now = [NOW]
    local, lan, telemetry = clients(p=policy(device_burst=10), clock=lambda: now[0])
    assert post(local).status_code == 202
    first = get(lan)
    direct = get(local)
    assert first.content == direct.content
    assert first.headers["etag"] == direct.headers["etag"]
    assert Snapshot.model_validate(first.json()).simulated is False
    assert get(lan, headers={"If-None-Match": first.headers["etag"]}).status_code == 304
    now[0] += 180
    stale = get(lan, headers={"If-None-Match": first.headers["etag"]})
    assert stale.status_code == 200 and stale.json()["status"] == "UNKNOWN"
    assert "DATOS CADUCADOS" in stale.text and "CPU 20%" not in stale.text
    assert post(local, now[0]).status_code == 202
    assert get(lan).json()["status"] == "HEALTHY"
    assert telemetry.state["counts"]["collector_accepted"] == 2
    assert telemetry.state["counts"]["device_query"] == 4
    restarted, restarted_lan, _ = clients()
    assert get(restarted_lan).json()["status"] == "UNKNOWN"
    assert post(restarted).status_code == 202
    assert get(restarted_lan).json()["status"] == "HEALTHY"


@pytest.mark.parametrize(
    "method,path,headers,body,code",
    [
        ("POST", "/api/v1/collectors/workstation/metrics", {}, b"private", 404),
        ("GET", "/docs", {}, None, 404),
        ("GET", "/api/v1/devices/other/status", {}, None, 404),
        ("GET", "/api/v1/devices/badge/status?fault=json", {}, None, 404),
        (
            "GET",
            "/api/v1/devices/badge/status",
            {"Authorization": "Bearer " + COLLECTOR},
            None,
            401,
        ),
        ("GET", "/api/v1/devices/badge/status", {"Host": "foreign.test:8443"}, None, 400),
        ("GET", "/api/v1/devices/badge/status", {"Content-Length": "8"}, b"anything", 400),
        ("GET", "/api/v1/devices/badge/status", {"If-None-Match": "unbounded-invalid"}, None, 400),
        ("GET", "/api/v1/devices/badge/status", {"X-Large": "x" * 8193}, None, 431),
        (
            "GET",
            "/api/v1/devices/badge/status",
            {"Authorization": "Bearer " + "x" * 200},
            None,
            401,
        ),
    ],
)
def test_lan_exposes_only_bounded_authorized_status(method, path, headers, body, code):
    local, lan, _ = clients()
    post(local)
    reply = lan.request(
        method, path, headers={"Authorization": "Bearer " + DEVICE} | headers, content=body
    )
    assert reply.status_code == code
    assert "CPU" not in reply.text and COLLECTOR not in reply.text


def test_duplicate_auth_encoded_path_and_websocket_rejected():
    _, lan, _ = clients()
    assert (
        lan.get(
            "/api/v1/devices/badge/status",
            headers=[("Authorization", "Bearer " + DEVICE), ("Authorization", "Bearer " + DEVICE)],
        ).status_code
        == 401
    )
    assert get(lan, headers={"If-None-Match": '"' + "a" * 64 + '"'}).status_code == 200
    assert (
        lan.get(
            "/api/v1/devices/%62adge/status", headers={"Authorization": "Bearer " + DEVICE}
        ).status_code
        == 404
    )
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with lan.websocket_connect("/api/v1/devices/badge/status"):
            pass


def test_network_lost_and_recovered_without_disabling_local_ingestion():
    approved = [False]
    local, lan, telemetry = clients(authorized=lambda: approved[0])
    assert post(local).status_code == 202
    assert get(lan).status_code == 503
    approved[0] = True
    assert get(lan).status_code == 200
    approved[0] = False
    assert get(lan).status_code == 503
    assert telemetry.state["counts"]["network_unavailable"] == 2


def test_network_guard_rechecked_before_response_and_no_payload_leak():
    calls = iter([True, False])
    local, lan, _ = clients(authorized=lambda: next(calls))
    post(local)
    reply = get(lan)
    assert reply.status_code == 503 and "CPU" not in reply.text


def test_device_and_global_limits_do_not_grow_with_attacker_identities():
    _, lan, telemetry = clients(p=policy(edge_burst=3, device_burst=1))
    assert get(lan).status_code == 200
    assert get(lan).status_code == 429
    assert get(lan, headers={"Authorization": "Bearer bad"}).status_code == 401
    assert get(lan).status_code == 429
    assert telemetry.state["counts"]["rate_limited"] == 2


def test_lease_expiry_suspend_policy_change_and_private_file_boundary(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "lease.json"
    p = policy()
    write_private(
        path,
        dict(
            schema_version=1,
            policy_sha256=p.fingerprint(),
            observed_boot_seconds=100.0,
            allowed=True,
        ),
    )
    assert lease_valid(path, p, lambda: 114.9)
    assert not lease_valid(path, p, lambda: 115.0)
    assert not lease_valid(path, p, lambda: 99.0)
    assert not lease_valid(path, p, lambda: 10000.0)  # CLOCK_BOOTTIME includes suspend.
    assert not lease_valid(path, policy(device_burst=3), lambda: 101.0)
    path.chmod(0o644)
    assert not lease_valid(path, p, lambda: 101.0)
    path.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(path)
    assert not lease_valid(link, p, lambda: 101.0)


def network_reader(p, change=None):
    calls = []

    def read(*args):
        calls.append(args)
        assert args[0] in ("ip", "nmcli", "firewall-cmd", "busctl")
        assert not any(
            v in args for v in ("add", "del", "modify", "up", "down", "--reload", "--permanent")
        )
        if args[:3] == ("ip", "-j", "address"):
            return json.dumps(
                [
                    dict(
                        flags=["UP"],
                        addr_info=[
                            dict(local=p.address if change != "ip" else "10.23.42.99", prefixlen=24)
                        ],
                    )
                ]
            )
        if args[:3] == ("ip", "-j", "route"):
            return json.dumps([dict(dev=p.interface if change != "route" else "other-interface")])
        if args[0] == "nmcli":
            if "GENERAL.CON-UUID" in args:
                return p.connection_uuid if change != "profile" else "other-private-profile"
            return "SYNTHETIC LAB" if change != "ssid" else "OTHER PRIVATE NETWORK"
        if "--get-zone-of-interface=" + p.interface in args:
            return p.firewall_zone
        if "--list-all" in args:
            return "reviewed synthetic rules" if change != "firewall" else "changed rules"
        if "--list-ports" in args:
            return "8443-8474/tcp" if change == "broad_port" else ""
        if any(a.startswith("--query-rich-rule=") for a in args):
            if change == "missing_rule":
                raise subprocess.CalledProcessError(1, args)
            return "yes"
        raise AssertionError("Unexpected read command")

    return read, calls


@pytest.mark.parametrize(
    "change",
    [None, "ip", "route", "profile", "ssid", "firewall", "broad_port", "missing_rule", "dns"],
)
def test_host_guard_read_only_checks_and_fail_closed(tmp_path, change):
    tmp_path.chmod(0o700)
    p = policy()
    read, calls = network_reader(p, change)

    def resolver(*a, **kw):
        return [(None, None, None, None, (p.address if change != "dns" else "10.23.42.99", 8443))]

    path = tmp_path / "lease.json"
    assert lan_guard.refresh(p, path, reader=read, clock=lambda: 100.0, resolver=resolver) is (
        change is None
    )
    assert lease_valid(path, p, lambda: 101.0) is (change is None)
    assert all("PRIVATE" not in " ".join(c) for c in calls)


def test_telemetry_bounded_concurrent_private_and_failure_is_not_data_failure(
    tmp_path, monkeypatch
):
    tmp_path.chmod(0o700)
    target = tmp_path / "state.json"
    telemetry = Telemetry(target, clock=lambda: NOW)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: telemetry.emit("auth_rejected"), range(40)))
    telemetry.emit("collector_accepted", collected_at=NOW - 20, ttl_seconds=180)
    state = json.loads(target.read_text())
    assert state["counts"]["auth_rejected"] == 40 and target.stat().st_mode & 0o077 == 0
    assert target.stat().st_size < 8192
    assert view(state, NOW)["collector_sample_age_seconds"] == 20
    assert not view(state, NOW + 180)["sample_fresh"]
    assert view(state, NOW)["process_liveness"] == "not_proven_by_file"
    with pytest.raises(ValueError):
        view(state | {"counts": {"private": "DO NOT PRINT"}}, NOW)
    with pytest.raises(ValueError):
        telemetry.emit("unknown", token="PRIVATE")

    def full(*args):
        raise OSError("PRIVATE PATH")

    monkeypatch.setattr("infrabadge_gateway.lan_telemetry.write_private", full)
    telemetry.emit("device_query")
    assert telemetry.state["telemetry_write_errors"] == 1


def preparation_module():
    spec = importlib.util.spec_from_file_location("m31_prepare", ROOT / "tools/m31/prepare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_bundle_is_explicit_private_reproducible_and_no_wildcards(tmp_path):
    module = preparation_module()
    result = module.render(policy(), tmp_path / "candidate")
    other = module.render(policy(), tmp_path / "other")
    assert result["status"] == "rendered_not_installed" and not result["host_changed"]
    assert result["guard_zip_sha256"] == other["guard_zip_sha256"]
    bundle = tmp_path / "candidate"
    unit = (bundle / "infrabadge-gateway.container").read_text()
    assert "PublishPort=127.0.0.1:8443:8443" in unit
    assert "PublishPort=10.23.42.10:8443:8444" in unit
    assert "0.0.0.0" not in unit and "Network=host" not in unit and "--privileged" not in unit
    assert "ContainerName=infrabadge-gateway-m3" in unit
    assert all(p.stat().st_mode & 0o077 == 0 for p in bundle.iterdir())
    plan = json.loads((bundle / "deployment-plan.json").read_text())
    assert plan["requires_deployment_authorization"] and not plan["changes_applied"]
    assert plan["proposed_route_add"][3:] == plan["proposed_route_delete"][3:]
    command = [sys.executable, "-I", str(bundle / "infrabadge-lan-guard.pyz"), "--help"]
    assert subprocess.run(command, capture_output=True, timeout=10).returncode == 0
    with pytest.raises(ValueError):
        module.render(policy(), bundle)
    with pytest.raises(ValueError):
        module.render(policy(), ROOT / "results/m31-not-allowed")


def test_policy_private_loading_duplicate_fields_and_unknown_keys(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "policy.json"
    write_private(path, dataclasses.asdict(policy()))
    assert LanPolicy.load(path).fingerprint() == policy().fingerprint()
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError):
        LanPolicy.load(path)


@pytest.mark.parametrize("match", [True, False])
def test_mdns_guard_is_bound_to_interface_without_global_dns_fallback(tmp_path, monkeypatch, match):
    tmp_path.chmod(0o700)
    p = policy(hostname="badge-gateway.local")
    base, calls = network_reader(p)
    monkeypatch.setattr(lan_guard.socket, "if_nametoindex", lambda interface: 7)

    def read(*args):
        if args[0] == "busctl":
            calls.append(args)
            assert args[-5:] == ("7", "0", p.hostname, "0", "0")
            return json.dumps(
                dict(data=[7, 0, p.hostname, 0, p.address if match else "10.23.42.99", 0])
            )
        return base(*args)

    def forbidden(*args, **kwargs):
        raise AssertionError("No global resolver fallback for mDNS")

    assert (
        lan_guard.refresh(
            p, tmp_path / "lease.json", reader=read, clock=lambda: 100.0, resolver=forbidden
        )
        is match
    )
    assert any(call[0] == "busctl" for call in calls)


def test_slow_guard_denies_lease_and_rate_budget_recovers(tmp_path):
    from infrabadge_gateway.lan_edge import Bucket

    tmp_path.chmod(0o700)
    p = policy()
    read, _ = network_reader(p)
    ticks = iter([100.0, 107.0])
    assert not lan_guard.refresh(
        p,
        tmp_path / "lease.json",
        reader=read,
        clock=lambda: next(ticks),
        resolver=lambda *a, **kw: [(None, None, None, None, (p.address, 8443))],
    )
    now = [100.0]
    bucket = Bucket(6, 2, clock=lambda: now[0])
    assert bucket.take() and bucket.take() and not bucket.take()
    now[0] += 9
    assert not bucket.take()
    now[0] += 1
    assert bucket.take() and not bucket.take()
    now[0] += 10000
    assert bucket.take() and bucket.take() and not bucket.take()
