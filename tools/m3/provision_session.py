#!/usr/bin/env python3
"""One normal-M3 USB provisioning, no esptool/reset/flash or autonomous reopen."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/m2"))
from provision import read_private, wire

SDK = "b774170ff46c393eeb5e495ea37936038d3f4f4f"


def save(path, state):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(temporary, path)


def provision_channel(channel, value, state, persist, deadline):
    """The only TX path: READY -> one private frame -> OK. No reset command."""
    while time.monotonic() < deadline:
        line = channel.readline(4096).strip()
        if line == b"IBPROV_READY" and not state["attempted"]:
            state["attempted"] = True
            persist()
            channel.write(wire(value, int(time.time())))
            channel.flush()
            print(
                "Configuración enviada una vez. Soltá BOOT; después no tocar botones ni USB.",
                flush=True,
            )
        elif line == b"IBPROV_OK" and state["attempted"]:
            state["ack"] = True
            persist()
            return
        elif line in (b"IBPROV_ERROR", b"IBPROV_TIMEOUT"):
            raise RuntimeError("provision_rejected_no_retry")
    raise RuntimeError("provision_ack_not_observed_no_retry")


def await_provision(ports, connect, value, state, persist, deadline, recoverable):
    """Reconnect only BEFORE any TX; never reuse a handle across deep sleep."""
    identity = None
    while time.monotonic() < deadline:
        found = ports()
        if not found:
            time.sleep(0.1)
            continue
        candidate = found[0].serial_number
        if not candidate or (identity is not None and candidate != identity):
            raise RuntimeError("usb_identity_missing_or_changed")
        identity = candidate  # In memory only; never persist hardware identifiers.
        channel = None
        try:
            channel = connect(found[0].device)
            state["serial_opened"] = True
            state["pre_tx_opens"] = state.get("pre_tx_opens", 0) + 1
            persist()
            provision_channel(channel, value, state, persist, deadline)
            return channel
        except recoverable:
            if channel:
                channel.close()
            if state["attempted"]:
                raise  # TX may have reached the board: no reopen or resend.
            state["pre_tx_disconnects"] = state.get("pre_tx_disconnects", 0) + 1
            persist()
            if state["pre_tx_disconnects"] >= 4:
                raise RuntimeError("pre_tx_usb_unstable_no_configuration_sent") from None
            print(
                "USB reconectando antes del envío; mantené BOOT hasta Configuración enviada.",
                flush=True,
            )
            time.sleep(0.2)
        except BaseException:
            if channel:
                channel.close()
            raise
    raise RuntimeError("pre_tx_deadline_no_configuration_sent")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() == 0 or not (args.private / "execution.json").exists():
        raise RuntimeError("normal_user_authorized_parent_required")
    if (
        subprocess.check_output(
            ["git", "-C", os.environ["IDF_PATH"], "rev-parse", "HEAD"], text=True
        ).strip()
        != SDK
    ):
        raise RuntimeError("sdk_mismatch")
    record = args.out / "provision.json"
    state = dict(
        status="started",
        attempted=False,
        ack=False,
        serial_opened=False,
        firmware_written=False,
        autonomous_usb_reopens=0,
    )
    with record.open("x") as stream:
        json.dump(state, stream)
    import serial
    from serial.tools import list_ports

    def ports():
        found = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x303A, 0x1001)]
        if len(found) > 1:
            raise RuntimeError("ambiguous_usb_target")
        return found

    channel = None
    with (Path(tempfile.gettempdir()) / ("infrabadge-physical-" + str(os.getuid()) + ".lock")).open(
        "a"
    ) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            end = time.monotonic() + 35
            while ports() and time.monotonic() < end:
                time.sleep(0.1)
            if ports():
                raise RuntimeError("wait_for_sleep_no_reset_requested")
            print(
                "LISTO BOOT: mantené BOOT pulsado hasta Configuración enviada y soltalo. No PWR/reset.",
                flush=True,
            )
            stamp = json.loads((args.out / "host-preflight.json").read_text())
            if not 0 <= time.time() - stamp["utc_checked_epoch"] < 180:
                raise RuntimeError("host_utc_preflight_too_old")

            def connect(port):
                candidate = serial.Serial(
                    port=None,
                    baudrate=115200,
                    timeout=0.2,
                    write_timeout=3,
                    exclusive=True,
                )
                candidate.port = port
                candidate.dtr = False
                candidate.rts = False
                try:
                    candidate.open()
                except BaseException:
                    candidate.close()
                    raise
                return candidate

            channel = await_provision(
                ports,
                connect,
                read_private(args.private / "device.json"),
                state,
                lambda: save(record, state),
                time.monotonic() + 60,
                (serial.SerialException, OSError),
            )
            print(
                "IBPROV_OK. Esperando cierre USB; no se volverá a abrir durante la prueba autónoma.",
                flush=True,
            )
            end = time.monotonic() + 35
            while ports() and time.monotonic() < end:
                time.sleep(0.1)
            state["usb_disappeared_after_ack"] = not ports()
            if not state["usb_disappeared_after_ack"]:
                raise RuntimeError("usb_disappearance_not_observed")
            state["status"] = "completed"
        except (Exception, KeyboardInterrupt) as error:
            state["status"] = "partial"
            state["stop_class"] = type(error).__name__
        finally:
            if channel:
                channel.close()
            save(record, state)
            print(
                "Provisión: " + state["status"] + "; sin carga ni reintento. Dejá BOOT suelto.",
                flush=True,
            )
    return 0 if state["status"] == "completed" else 1


if __name__ == "__main__":

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit("USB preparation stopped; preserve private results. No retry.") from None
