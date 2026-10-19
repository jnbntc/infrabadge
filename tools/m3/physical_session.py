#!/usr/bin/env python3
"""New approved M3 lab session: provisioning only, then no USB. No firmware load.

Uses the installed localhost gateway unchanged, through the opt-in TLS observer.
Exact temporary reply routing is independently bounded; collector pause/recovery
is restored in finally. Optical observations are collected separately, never as
blocking terminal questions during cleanup-critical phases.
"""

import argparse
import datetime as dt
import json
import os
import select
import signal
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/m2"))


def run(*args, timeout=20):
    return subprocess.check_output(
        args, stderr=subprocess.DEVNULL, text=True, timeout=timeout
    ).strip()


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, path)


def route_child(interface, address, network):
    from try_local_route import check_scope, reply_route, rule_command

    if os.geteuid() != 0:
        raise RuntimeError("root_only_for_exact_route")
    check_scope(interface, address, network)
    attempted = False
    try:
        attempted = True
        subprocess.run(
            rule_command("add", address, network), capture_output=True, check=True, timeout=5
        )
        if reply_route(address, network) != interface:
            raise RuntimeError("return_route_not_wifi")
        print("M3_ROUTE_READY", flush=True)
        end = time.monotonic() + 1200
        while time.monotonic() < end:
            readable, _, _ = select.select([sys.stdin], [], [], 0.5)
            if readable:
                break
    finally:
        if attempted:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            removed = subprocess.run(
                rule_command("del", address, network), capture_output=True, timeout=5
            )
            occupied = any(
                r.get("priority") == 5100 for r in json.loads(run("ip", "-j", "rule", "show"))
            )
            if removed.returncode or occupied:
                raise RuntimeError("exact_route_cleanup_unconfirmed")
            print("M3_ROUTE_REMOVED", flush=True)


def cleanup(state, route, server, paused, restore_guard):
    """Each resource gets cleanup even if another resource fails."""
    try:
        if paused:
            run("systemctl", "--user", "start", "infrabadge-collector.timer")
        state["collector_restored"] = (
            run("systemctl", "--user", "is-active", "infrabadge-collector.timer") == "active"
        )
    except (OSError, subprocess.SubprocessError):
        state["collector_restored"] = False
    if restore_guard and state["collector_restored"]:
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", restore_guard + ".timer"],
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        state["observer_stopped"] = server is None or server.poll() is not None
    except (OSError, subprocess.SubprocessError):
        state["observer_stopped"] = False
    try:
        if route is not None:
            route.stdin.close()
            route.stdin = None
            rest, _ = route.communicate(timeout=15)
            state["route_cleanup_confirmed"] = route.returncode == 0 and "M3_ROUTE_REMOVED" in rest
        else:
            state["route_cleanup_confirmed"] = True
    except (OSError, subprocess.SubprocessError):
        # The privileged child still owns its independent maximum20min timer.
        state["route_cleanup_confirmed"] = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path)
    parser.add_argument("--authorized-m3-observation", action="store_true")
    parser.add_argument("--route-child", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.route_child:
        route_child(*args.route_child)
        return 0
    if not args.private or os.geteuid() == 0:
        parser.error("Normal user and --private required")
    from prepare_observer import private_bytes, require_host, write_private

    require_host()

    plan = json.loads(private_bytes(args.private / "plan.json", 8192))
    observer = json.loads(private_bytes(args.private / "observer.json", 8192))
    if (
        plan["authorization"] != "required_new_m3_observation_session"
        or plan["board_flash_permitted"]
        or plan["maximum_seconds"] != 1200
        or plan["route_priority"] != 5100
        or plan["tcp_source_port"] != 8443
        or plan["provision_count"] != 1
        or observer["listen_address"] != plan["address"]
    ):
        raise RuntimeError("wrong_session_scope")
    if (args.private / "execution.json").exists():
        raise RuntimeError("session_consumed_no_retry")
    if not args.authorized_m3_observation:
        print(
            "Preview: one UTC provisioning, temporary LAN/route, collector pause/recovery. No firmware load or service changes executed."
        )
        return 0
    if not sys.stdin.isatty():
        raise RuntimeError("normal_terminal_for_sudo_required")
    if run("timedatectl", "show", "-p", "NTPSynchronized", "--value") != "yes":
        raise RuntimeError("trusted_host_utc_required")
    if run("systemctl", "--user", "is-active", "infrabadge-collector.timer") != "active":
        raise RuntimeError("collector_timer_must_be_active")
    from provision import read_private

    device = read_private(args.private / "device.json")
    uuid = run(
        "nmcli", "--escape", "no", "-g", "GENERAL.CON-UUID", "device", "show", plan["interface"]
    )
    if (
        run(
            "nmcli",
            "--escape",
            "no",
            "-g",
            "802-11-wireless.ssid",
            "connection",
            "show",
            "uuid",
            uuid,
        )
        != device["ssid"]
    ):
        raise RuntimeError("active_ssid_changed_no_board_access")
    del device
    if plan["route_required"]:
        from try_local_route import check_scope

        check_scope(plan["interface"], plan["address"], plan["network"])
        if subprocess.run(["sudo", "-v"]).returncode:
            raise RuntimeError("route_privilege_not_available")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "results" / ("m3-observation-" + stamp)
    out.mkdir(mode=0o700)
    write_private(
        args.private / "execution.json",
        dict(results=str(out), started_utc=stamp, firmware_write_permitted=False),
    )
    state = dict(
        status="running",
        phase="preparing",
        firmware_written=False,
        serial_reopens_during_autonomous_phase=0,
        optical_confirmation="separate_operator_evidence_required",
        exact_wake_cause_verified=False,
        electrical_measurements="DEFERRED",
        route_cleanup_confirmed=False,
        collector_restored=False,
        observer_stopped=False,
    )
    save(out / "result.json", state)
    print("Resultados: " + str(out), flush=True)
    route = server = None
    paused = False
    restore_guard = None
    overall_end = time.monotonic() + 1080

    def phase(name):
        state["phase"] = name
        save(out / "result.json", state)
        print("M3: " + name, flush=True)

    def next_event(after, predicate, seconds):
        end = min(overall_end, time.monotonic() + seconds)
        while time.monotonic() < end:
            journal = args.private / "observations.json"
            if journal.exists():
                for event in json.loads(journal.read_text())["events"]:
                    if (
                        event["sequence"] > after
                        and event["outcome"] == "completed"
                        and predicate(event)
                    ):
                        return event
            if server.poll() is not None:
                raise RuntimeError("observer_stopped_early")
            time.sleep(0.5)
        raise RuntimeError("phase_deadline_no_write_retry")

    try:
        if plan["route_required"]:
            route = subprocess.Popen(
                [
                    "sudo",
                    "-n",
                    str(Path(sys.executable).resolve()),
                    str(Path(__file__).resolve()),
                    "--route-child",
                    plan["interface"],
                    plan["address"],
                    plan["network"],
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            ready, _, _ = select.select([route.stdout], [], [], 10)
            if not ready or route.stdout.readline().strip() != "M3_ROUTE_READY":
                raise RuntimeError("route_not_ready_no_board_access")
        server = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tools/m3/observe_gateway.py"),
                "--private",
                str(args.private),
                "--authorized-temporary-observer",
            ]
        )
        context = ssl.create_default_context(cafile=observer["ca_file"])
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        end = time.monotonic() + 10
        ready = False
        while time.monotonic() < end and server.poll() is None:
            try:
                with socket.create_connection((plan["address"], 8443), timeout=1) as channel:
                    with context.wrap_socket(channel, server_hostname=plan["hostname"]):
                        pass  # TLS handshake only: never creates a fake device GET.
                ready = True
                break
            except OSError:
                time.sleep(0.2)
        if not ready:
            raise RuntimeError("observer_tls_not_ready")
        save(out / "host-preflight.json", dict(utc_checked_epoch=time.time()))
        phase("provisioning_once")
        code = subprocess.run(
            [
                "distrobox",
                "enter",
                "--name",
                "iot-dev",
                "--",
                "/usr/local/bin/idf-env",
                "python3",
                str(ROOT / "tools/m3/provision_session.py"),
                "--private",
                str(args.private),
                "--out",
                str(out),
            ],
            timeout=160,
        ).returncode
        if code:
            raise RuntimeError("provisioning_incomplete_no_retry")
        phase("first_real_query")
        first = next_event(0, lambda e: e["control"] == "fresh" and e["http_status"] == 200, 60)
        state["first_real_query"] = first
        phase("waiting_autonomous_query_no_usb")
        autonomous = next_event(
            first["sequence"],
            lambda e: e["http_status"] in (200, 304)
            and e["received_at"] >= first["received_at"] + 5,
            240,
        )
        state["autonomous_query"] = autonomous
        phase("collector_paused")
        restore_guard = "infrabadge-m3-collector-guard-" + stamp.lower()
        run(
            "systemd-run",
            "--user",
            "--unit=" + restore_guard,
            "--on-active=7m",
            "--timer-property=AccuracySec=1s",
            "systemctl",
            "--user",
            "start",
            "infrabadge-collector.timer",
        )
        paused = True
        run(
            "systemctl",
            "--user",
            "stop",
            "infrabadge-collector.timer",
            "infrabadge-collector.service",
        )
        stale = next_event(
            autonomous["sequence"],
            lambda e: e["control"] == "stale" and e["state"] == "UNKNOWN",
            310,
        )
        state["stale_response"] = stale
        phase("stale_response_delivered_observe_screen")
        time.sleep(45)
        run("systemctl", "--user", "start", "infrabadge-collector.timer")
        paused = False
        phase("collector_resumed_waiting_recovery")
        recovery = next_event(stale["sequence"], lambda e: e["control"] == "fresh", 310)
        state["recovery_response"] = recovery
        phase("recovery_response_delivered_observe_screen")
        time.sleep(30)
        state["status"] = "autonomous_stale_recovery_observed_optical_evidence_separate"
    except (Exception, KeyboardInterrupt) as error:
        state["status"] = "partial"
        state["stop_class"] = type(error).__name__
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        cleanup(state, route, server, paused, restore_guard)
        if not all(
            state[k] for k in ("collector_restored", "observer_stopped", "route_cleanup_confirmed")
        ):
            state["scenario_status"] = state["status"]
            state["status"] = "cleanup_incomplete"
        state["phase"] = "finished"
        save(out / "result.json", state)
        print("Estado: " + state["status"] + ". Resultados: " + str(out), flush=True)
        print(
            "No se flasheó. USB quedó cerrado durante las consultas autónomas. No repetir la sesión consumida.",
            flush=True,
        )
    return (
        0
        if state["status"] == "autonomous_stale_recovery_observed_optical_evidence_separate"
        else 1
    )


if __name__ == "__main__":

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(
            "Session stopped; preserve private results, no automatic provisioning retry."
        ) from None
