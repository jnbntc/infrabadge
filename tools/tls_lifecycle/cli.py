"""Inert until installed/authorized. No generic service controller or CA rotation."""

import argparse
import hashlib
import http.client
import json
import os
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "permanent_edge"))

import ib_edge_lab as lab
import lifecycle as engine
import notifications
import pki

CONFIG = Path("/etc/infrabadge-tls/config.json")
UNIT = Path("/etc/systemd/system/infrabadge-edge-home.service")
PROBE = Path("/etc/infrabadge-edge-home/probe.json")
GUARD = "infrabadge-edge-home-tls-recovery"


def synchronized():
    return (
        pki.command(
            [
                "/usr/bin/timedatectl",
                "show",
                "--property=NTPSynchronized",
                "--value",
            ]
        ).strip()
        == b"yes"
    )


def trusted_executable(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("executable_symlink")
    for item in (path, *path.parents):
        info = item.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("executable_owner_mode")
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("executable_required")


class Host:
    unit_path = UNIT

    def __init__(self, config):
        self.config = config
        self.guard_created = False

    def check(self):
        for item in (UNIT, UNIT.parent):
            info = item.lstat()
            if item.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("service_unit_owner")
        if pki.digest(UNIT) != self.config["unit_sha256"]:
            raise ValueError("service_unit_drift")
        # Hash the effective systemd definition too: a new drop-in is configuration drift.
        effective = pki.command(["/usr/bin/systemctl", "cat", engine.SERVICE])
        if hashlib.sha256(effective).hexdigest() != self.effective_digest:
            raise ValueError("effective_unit_drift")

    @property
    def effective_digest(self):
        return engine.load(CONFIG.parent / "runtime.json")["effective_unit_sha256"]

    def active(self):
        return pki.command(["/usr/bin/systemctl", "is-active", engine.SERVICE]).strip() == b"active"

    def stop(self):
        pki.command(["/usr/bin/systemctl", "stop", engine.SERVICE], timeout=20)
        if (
            pki.command(
                ["/usr/bin/systemctl", "show", "-p", "ActiveState", "--value", engine.SERVICE]
            ).strip()
            != b"inactive"
        ):
            raise ValueError("stop_not_confirmed")

    def start(self):
        pki.command(["/usr/bin/systemctl", "start", engine.SERVICE], timeout=30)

    def probe(self):
        # Pin probe configuration and actual served leaf, then reuse v2/ETag/TTL checks.
        self.check()
        engine.verify_runtime(self.config, UNIT)
        runtime = engine.load(CONFIG.parent / "runtime.json")
        probe_path = PROBE
        raw = pki.private(probe_path, self.config["owner_uid"])
        if hashlib.sha256(raw).hexdigest() != runtime["probe_config_sha256"]:
            raise ValueError("probe_configuration_drift")
        probe = json.loads(raw)
        url = urlsplit(probe["url"])
        cert, _, ca = engine.paths(self.config)
        if (
            url.scheme != "https"
            or url.hostname not in self.config["sans"]
            or url.port != 8443
            or probe["ca_file"] != str(ca)
        ):
            raise ValueError("approved_probe_origin")
        context = ssl.create_default_context(cafile=str(ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = http.client.HTTPSConnection(url.hostname, 8443, context=context, timeout=4)
        try:
            connection.connect()
            served = connection.sock.getpeercert(binary_form=True)
            expected = ssl.PEM_cert_to_DER_cert(cert.read_text())
            if hashlib.sha256(served).digest() != hashlib.sha256(expected).digest():
                raise ValueError("served_leaf_mismatch")
        finally:
            connection.close()
        # Credential remains owned by Edge; root never impersonates badge.
        release = Path(__file__).resolve().parents[2]
        pki.command(
            [
                "/usr/sbin/runuser",
                "-u",
                "ibedgehome",
                "--",
                str(release / "venv/bin/python"),
                "-I",
                "-B",
                str(release / "tools/permanent_edge/ib_edge_lab.py"),
                "probe",
                "--config",
                "/etc/infrabadge-edge-home/probe.json",
            ],
            timeout=10,
        )

    def arm(self):
        # A fresh unique guard per transaction; retain evidence until reviewed.
        pki.command(
            [
                "/usr/bin/systemd-run",
                "--unit=" + GUARD,
                "--collect",
                "--on-boot=" + str(time.monotonic() + 120) + "s",
                "--timer-property=AccuracySec=1s",
                "--property=Type=oneshot",
                "--property=TimeoutStartSec=60s",
                "--property=UMask=0077",
                "--property=NoNewPrivileges=yes",
                "--property=PrivateTmp=yes",
                "--property=CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_SETUID CAP_SETGID",
                "--property=ProtectHome=yes",
                "--property=ProtectSystem=strict",
                "--property=ReadWritePaths=/var/lib/infrabadge-tls /etc/infrabadge-edge-home",
                "/usr/bin/python3",
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "recover",
                "--execute-authorized-renewal",
            ]
        )
        self.guard_created = True
        pki.command(["/usr/bin/systemctl", "is-active", GUARD + ".timer"])
        result = (
            pki.command(
                [
                    "/usr/bin/busctl",
                    "get-property",
                    "org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1/unit/" + GUARD.replace("-", "_2d") + "_2etimer",
                    "org.freedesktop.systemd1.Timer",
                    "NextElapseUSecMonotonic",
                ]
            )
            .decode()
            .split()
        )
        if (
            len(result) != 2
            or result[0] != "t"
            or not 110 <= int(result[1]) / 1e6 - time.monotonic() <= 125
        ):
            raise ValueError("independent_deadline_not_verified")

    def disarm(self):
        if self.guard_created:
            pki.command(["/usr/bin/systemctl", "stop", GUARD + ".timer"])


def issue(config, request):
    executable = config["issuer_executable"]
    trusted_executable(executable)
    pki.private(config["issuer_config"], 0)
    # CSR public bytes on stdin; private key stays in the private run directory.
    return pki.command([executable, "--config", config["issuer_config"]], data=request, timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("monitor", "evaluate", "verify", "notify", "renew", "recover")
    )
    parser.add_argument("--execute-authorized-renewal", action="store_true")
    parser.add_argument("--execute-authorized-notifications", action="store_true")
    args = parser.parse_args()
    try:
        if os.getuid() != 0:
            raise ValueError("dedicated_root_oneshot_only")
        if args.mode in ("renew", "recover") and not args.execute_authorized_renewal:
            raise ValueError("renewal_authorization_required")
        if args.mode == "notify" and not args.execute_authorized_notifications:
            raise ValueError("channel_authorization_required")
        os.umask(0o077)
        config = engine.settings(engine.load(CONFIG))
        if (
            config["directory"] != "/etc/infrabadge-edge-home"
            or config["state_directory"] != "/var/lib/infrabadge-tls"
        ):
            raise ValueError("fixed_casa_scope")
        directory = Path(config["state_directory"])
        with engine.locked(directory):
            state_path = directory / "state.json"
            state = engine.load(state_path) if state_path.exists() else {}
            now = time.time()
            engine.clock_ok(state, now, synchronized())
            result = {"mode": args.mode}
            if args.mode == "monitor":
                result["certificates"] = engine.monitor(config, state, now)
            elif args.mode == "evaluate":
                cert, _, _ = engine.paths(config)
                _, after = pki.dates(cert)
                result["renewal_due"] = after - now <= config["renew_seconds"]
            elif args.mode == "verify":
                host = Host(config)
                host.check()
                host.probe()
                result["https_verified"] = True
            elif args.mode == "renew":
                try:
                    with lab.deadline(90):
                        result["result"] = engine.renew(
                            config, state, now, Host(config), lambda csr: issue(config, csr)
                        )
                except Exception:
                    notifications.emit(state, "renewal", "renewal_failed", now)
                    engine.save(state_path, state)
                    raise
            elif args.mode == "recover":
                if state.get("pending"):
                    transaction = engine.load(Path(state["pending"]) / "transaction.json")
                    try:
                        result["result"] = engine.restore(config, transaction, Host(config), now)
                    except Exception:
                        notifications.emit(state, "renewal", "renewal_failed", now)
                        engine.save(state_path, state)
                        raise
                    state.pop("pending", None)
                    notifications.emit(state, "renewal", "renewal_failed", now)
                else:
                    result["result"] = "no_pending_transaction"
            else:
                engine.check_stale(config, state, now)
                if config["notification"] is None:
                    raise ValueError("channel_not_configured")
                token = pki.private(config["notification"]["token_file"], 0, 256).decode().strip()
                result.update(notifications.deliver(state, config["notification"], token, now))
            engine.save(state_path, state)
            print(json.dumps(result, sort_keys=True))
        return (
            1
            if (
                result.get("failed")
                or result.get("exhausted")
                or any(x["status"] != "ok" for x in result.get("certificates", []))
            )
            else 0
        )
    except Exception:
        # Never print subprocess args, addresses, paths, OpenSSL errors or webhook bodies.
        print('{"event":"tls_lifecycle_error","action":"review_private_state"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
