"""One-write USB protocol and lab cleanup under failures, without hardware."""

import copy
import io
import json
import subprocess
import time
from collections import deque
from types import SimpleNamespace

import physical_session
import prepare_observer
import pytest
from infrabadge_gateway.lab import certificates
from provision_session import await_provision, provision_channel


def config():
    return dict(
        schema_version=1,
        device_id="badge-lab",
        ssid="PRIVATE-WIFI",
        wifi_password="private-password",
        gateway_url="https://localhost:8443",
        token="t" * 40,
        ca_pem="-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----",
        interval_seconds=900,
        wifi_timeout_ms=15000,
        http_timeout_ms=5000,
    )


@pytest.mark.parametrize("field", [None, "attempted", "ack", "firmware_written"])
def test_continuation_requires_proven_zero_tx(tmp_path, field):
    tmp_path.chmod(0o700)
    prior, out, current = (tmp_path / n for n in ("prior", "out", "current"))
    for p in (prior, out, current):
        p.mkdir(mode=0o700)
    scope = dict(
        interface="wifi",
        address="192.0.2.1",
        network="192.0.2.0/24",
        hostname="lab.local",
        maximum_seconds=1200,
        route_priority=5100,
        tcp_source_port=8443,
        board_flash_permitted=False,
        provision_count=1,
    )
    proof = dict(attempted=False, ack=False, firmware_written=False)
    if field:
        proof[field] = True
    for path, value in [
        (prior / "continuation.json", dict(private=str(current))),
        (prior / "execution.json", dict(results=str(out))),
        (prior / "plan.json", scope),
        (out / "provision.json", proof),
        (
            out / "result.json",
            dict(
                phase="finished",
                collector_restored=True,
                observer_stopped=True,
                route_cleanup_confirmed=True,
            ),
        ),
    ]:
        prepare_observer.write_private(path, value)
    plan = dict(scope, continuation_of=str(prior))
    if field:
        with pytest.raises(RuntimeError, match="proven_zero_tx"):
            physical_session.check_continuation(current, plan)
    else:
        physical_session.check_continuation(current, plan)
        plan["maximum_seconds"] = 1201
        with pytest.raises(RuntimeError, match="same_scope"):
            physical_session.check_continuation(current, plan)


class Channel:
    def __init__(self, lines):
        self.lines = deque(lines)
        self.transmitted = []
        self.closed = False

    def readline(self, _size):
        value = self.lines.popleft() if self.lines else b""
        if isinstance(value, Exception):
            raise value
        return value

    def write(self, data):
        self.transmitted.append(data)

    def flush(self):
        pass

    def close(self):
        self.closed = True


def test_reconnect_before_tx_only_with_same_identity():
    broken = Channel([OSError("private path")])
    ready = Channel([b"IBPROV_READY", b"IBPROV_OK"])
    channels = deque([broken, ready])
    port = SimpleNamespace(device="fixture-port", serial_number="private-id")
    state = dict(attempted=False, ack=False)
    result = await_provision(
        lambda: [port],
        lambda _: channels.popleft(),
        config(),
        state,
        lambda: None,
        time.monotonic() + 2,
        (OSError,),
    )
    assert result is ready and broken.closed and not ready.closed
    assert len(ready.transmitted) == 1 and not broken.transmitted
    assert state["pre_tx_opens"] == 2 and state["pre_tx_disconnects"] == 1


def test_disconnect_after_tx_never_reopens():
    broken = Channel([b"IBPROV_READY", OSError("private path")])
    port = SimpleNamespace(device="fixture-port", serial_number="private-id")
    calls = []
    state = dict(attempted=False, ack=False)

    def connect(_):
        calls.append(True)
        return broken

    with pytest.raises(OSError):
        await_provision(
            lambda: [port],
            connect,
            config(),
            state,
            lambda: None,
            time.monotonic() + 2,
            (OSError,),
        )
    assert state["attempted"] and not state["ack"]
    assert len(calls) == 1 and len(broken.transmitted) == 1 and broken.closed


def test_reconnect_rejects_changed_board_before_tx():
    identities = deque(["first-private-id", "other-private-id"])
    broken = Channel([OSError("disconnected")])
    calls = []

    def ports():
        return [SimpleNamespace(device="fixture-port", serial_number=identities.popleft())]

    def connect(_):
        calls.append(True)
        return broken

    with pytest.raises(RuntimeError, match="usb_identity_missing_or_changed"):
        await_provision(
            ports,
            connect,
            config(),
            dict(attempted=False, ack=False),
            lambda: None,
            time.monotonic() + 2,
            (OSError,),
        )
    assert len(calls) == 1 and not broken.transmitted


def test_pre_tx_reconnections_bounded():
    calls = []
    port = SimpleNamespace(device="fixture-port", serial_number="private-id")

    def connect(_):
        calls.append(True)
        raise OSError("unavailable")

    state = dict(attempted=False, ack=False)
    with pytest.raises(RuntimeError, match="pre_tx_usb_unstable"):
        await_provision(
            lambda: [port],
            connect,
            config(),
            state,
            lambda: None,
            time.monotonic() + 2,
            (OSError,),
        )
    assert len(calls) == 4 and not state["attempted"]


def test_ready_only_one_tx_repeated_ready_and_no_raw_log(capsys):
    channel = Channel(
        [
            b"raw private console data",
            b"IBPROV_OK",
            b"IBPROV_READY",
            b"IBPROV_READY",
            b"IBPROV_OK",
        ]
    )
    state = dict(attempted=False, ack=False)
    saved = []
    provision_channel(
        channel,
        config(),
        state,
        lambda: saved.append(copy.deepcopy(state)),
        time.monotonic() + 1,
    )
    assert state == dict(attempted=True, ack=True)
    assert len(channel.transmitted) == 1 and channel.transmitted[0].startswith(b"IBPROV1 ")
    assert saved == [dict(attempted=True, ack=False), dict(attempted=True, ack=True)]
    text = capsys.readouterr().out
    assert "private" not in text and "PRIVATE-WIFI" not in text and "t" * 40 not in text


@pytest.mark.parametrize(
    "lines,attempted",
    [
        ([], False),
        ([b"IBPROV_READY", b"IBPROV_ERROR"], True),
        ([b"IBPROV_READY", OSError("private serial detail")], True),
    ],
)
def test_failure_preserves_attempt_and_does_not_retry(lines, attempted):
    channel = Channel(lines)
    state = dict(attempted=False, ack=False)
    with pytest.raises((RuntimeError, OSError)):
        provision_channel(channel, config(), state, lambda: None, time.monotonic() + 0.01)
    assert state["attempted"] is attempted and not state["ack"]
    assert len(channel.transmitted) == int(attempted)


def test_no_tx_when_an_attempt_already_exists():
    channel = Channel([b"IBPROV_READY", b"IBPROV_READY", b"IBPROV_OK"])
    state = dict(attempted=True, ack=False)
    provision_channel(channel, config(), state, lambda: None, time.monotonic() + 1)
    assert channel.transmitted == []


class Process:
    def __init__(self, route=False):
        self.returncode = None
        self.stdin = io.StringIO()
        self.route = route
        self.stopped = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.stopped = True
        self.returncode = 0

    def wait(self, timeout):
        return self.returncode

    def communicate(self, timeout):
        assert self.stdin is None
        self.stopped = True
        self.returncode = 0
        return "M3_ROUTE_REMOVED", None


def test_failed_collector_restore_does_not_skip_observer_route(monkeypatch):
    def failed(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["systemctl"])

    monkeypatch.setattr(physical_session, "run", failed)
    server, route = Process(), Process(route=True)
    state = {}
    physical_session.cleanup(state, route, server, True, None)
    assert state == dict(
        collector_restored=False, observer_stopped=True, route_cleanup_confirmed=True
    )
    assert server.stopped and route.stopped


def test_failed_observer_stop_still_releases_route(monkeypatch):
    monkeypatch.setattr(physical_session, "run", lambda *a, **kw: "active")

    class Broken(Process):
        def terminate(self):
            raise OSError("private error")

    state = {}
    route = Process(route=True)
    physical_session.cleanup(state, route, Broken(), False, None)
    assert state == dict(
        collector_restored=True, observer_stopped=False, route_cleanup_confirmed=True
    )


def deployment(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_observer, "require_host", lambda: None)
    tmp_path.chmod(0o700)
    dep = tmp_path / "installed"
    dep.mkdir(mode=0o700)
    tls = dep / "tls"
    tls.mkdir(mode=0o700)
    ca, _, _ = certificates(tls)
    value = config()
    value["ca_pem"] = ca.read_text()
    device = tmp_path / "device.json"
    prepare_observer.write_private(device, value)
    import hashlib

    digest = hashlib.sha256(value["token"].encode()).hexdigest()
    gateway = tmp_path / "gateway.json"
    prepare_observer.write_private(
        gateway,
        dict(
            devices={"badge-lab": dict(node_id="workstation", token_sha256=[digest])},
            collectors={"workstation": dict(display_name="WORKSTATION", token_sha256=["a" * 64])},
        ),
    )
    prepare_observer.write_private(dep / "deployment.json", dict(gateway_config=str(gateway)))
    return dep, device


def test_loopback_preparation_skips_wifi_and_does_not_copy_wifi_secret(tmp_path, monkeypatch):
    dep, device = deployment(tmp_path, monkeypatch)

    def reads(*args):
        assert args[0] == "timedatectl"
        return "yes"

    monkeypatch.setattr(prepare_observer, "read", reads)
    output = tmp_path / "new"
    prepare_observer.prepare(output, dep, device, loopback_only=True)
    assert not (output / "device.json").exists()
    assert json.loads((output / "plan.json").read_text())["authorization"] == "loopback_check_only"
    assert "PRIVATE-WIFI" not in "".join(p.read_text() for p in output.iterdir())
    assert all(p.stat().st_mode & 0o077 == 0 for p in output.iterdir())


def test_physical_plan_checks_ssid_not_connection_alias(tmp_path, monkeypatch):
    dep, device = deployment(tmp_path, monkeypatch)
    monkeypatch.setattr(prepare_observer.socket, "if_nametoindex", lambda interface: 7)

    def reads(*args):
        if args[0] == "timedatectl":
            return "yes"
        if args[0] == "nmcli":
            if args[1:4] == ("-t", "-f", "DEVICE,TYPE,STATE"):
                return "wifi-test:wifi:connected"
            if "GENERAL.CON-UUID" in args:
                return "fixture-profile-uuid"
            if "802-11-wireless.ssid" in args:
                return "PRIVATE-WIFI"
            raise AssertionError("Must not inspect alias or credentials")
        if args[0] == "busctl":
            return json.dumps(dict(data=[7, 0, "localhost", 0, "192.0.2.10", 0]))
        if args[:3] == ("ip", "-j", "address"):
            return json.dumps(
                [
                    dict(
                        addr_info=[
                            dict(
                                family="inet",
                                scope="global",
                                local="192.0.2.10",
                                prefixlen=24,
                            )
                        ]
                    )
                ]
            )
        if args[:3] == ("ip", "-j", "route"):
            return json.dumps([dict(dev="wifi-test")])
        raise AssertionError("Unexpected read")

    monkeypatch.setattr(prepare_observer, "read", reads)
    output = tmp_path / "physical"
    prepare_observer.prepare(output, dep, device)
    assert json.loads((output / "plan.json").read_text())["route_required"] is False
    assert (output / "device.json").exists()


def test_existing_private_targets_are_not_overwritten(tmp_path):
    path = tmp_path / "private.json"
    prepare_observer.write_private(path, {"original": True})
    with pytest.raises(FileExistsError):
        prepare_observer.write_private(path, {"new": True})
    assert json.loads(path.read_text()) == dict(original=True)


@pytest.mark.parametrize("reply", ["wifi-test", "wrong-interface"])
def test_exact_route_cleanup_even_if_route_selection_fails(monkeypatch, reply):
    import sys

    import try_local_route

    commands = []
    monkeypatch.setattr(physical_session.os, "geteuid", lambda: 0)
    monkeypatch.setattr(try_local_route, "check_scope", lambda *args: None)
    monkeypatch.setattr(try_local_route, "reply_route", lambda *args: reply)

    def process(command, **kwargs):
        commands.append(command)
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setattr(physical_session.subprocess, "run", process)
    monkeypatch.setattr(physical_session, "run", lambda *args: "[]")
    monkeypatch.setattr(physical_session.select, "select", lambda *args: ([sys.stdin], [], []))
    if reply == "wifi-test":
        physical_session.route_child("wifi-test", "192.0.2.10", "192.0.2.0/24")
    else:
        with pytest.raises(RuntimeError):
            physical_session.route_child("wifi-test", "192.0.2.10", "192.0.2.0/24")
    assert commands[0] == [
        "ip",
        "rule",
        "add",
        "priority",
        "5100",
        "from",
        "192.0.2.10/32",
        "to",
        "192.0.2.0/24",
        "ipproto",
        "tcp",
        "sport",
        "8443",
        "lookup",
        "main",
    ]
    assert commands[1] == commands[0][:2] + ["del"] + commands[0][3:]
