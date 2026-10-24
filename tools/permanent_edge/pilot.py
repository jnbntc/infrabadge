"""Prepare a CASA trial. Installation requires a separate future root approval.

Never alters Core/collector units, SQLite, firewall, identities or certificates.
Approved certificates/tokens and a pinned locked release must already be staged.
"""

import argparse
import hashlib
import ipaddress
import json
import os
import pwd
import socket
import ssl
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ib_edge_lab as lab
import rollback

MATERIALS = ("server.pem", "server.key", "edge-ca.pem", "core-ca.pem", "edge.token", "probe.token")
CORE_UNITS = ("infrabadge-m32-core.service", "infrabadge-m32-collector.timer")


def configs(value, phase="loopback"):
    from infrabadge_gateway.distributed.edge import EdgeConfig

    value = lab.plan(value)
    if value["site"] != "home" or phase not in ("loopback", "lan"):
        raise ValueError("casa_core_only")
    base = "/etc/infrabadge-edge-home/"
    host = "127.0.0.1" if phase == "loopback" else value["edge_hostname"]
    edge = EdgeConfig(
        upstream="https://127.0.0.1:9443",
        device_ids=value["device_ids"],
        ca_file=base + "core-ca.pem",
        credential_file=base + "edge.token",
        public_hostname=host,
        public_port=8443,
        presentation_v2=True,
    ).model_dump()
    probe = dict(
        url="https://" + host + ":8443",
        ca_file=base + "edge-ca.pem",
        token_file=base + "probe.token",
        probe_device_id=value["probe_device_id"],
        minimum_leaf_seconds=604800,
    )
    return {
        "edge.json": json.dumps(edge, sort_keys=True) + "\n",
        "probe.json": json.dumps(probe, sort_keys=True) + "\n",
        "plan.json": json.dumps(value, sort_keys=True) + "\n",
    }


def prepare(value, directory, phase="loopback"):
    files = lab.render(value, lab.ROOT / "deploy/permanent_edge", phase) | configs(value, phase)
    directory = Path(directory)
    from infrabadge_gateway.distributed.private import private_parent

    private_parent(directory)
    directory.mkdir(mode=0o700)
    for name, text in files.items():
        fd = os.open(directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(text)
    return {"event": "casa_bundle", "files": len(files), "phase": phase, "installed": False}


def checked(run, args, timeout=15):
    result = run(args, check=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip()


def public_directory(path, owner=0):
    """Only NEW release directories get chmod; existing private paths are refused."""
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("release_symlink")
    created = False
    try:
        path.mkdir(mode=0o755)
        created = True
    except FileExistsError:
        pass
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if info.st_uid != owner:
            raise ValueError("release_owner")
        if created:
            os.fchmod(fd, 0o755)  # mkdir0755 alone becomes0700 under umask077.
        elif stat.S_IMODE(info.st_mode) != 0o755:
            raise ValueError("existing_release_directory_permissions")
    finally:
        os.close(fd)


def stage_release(value, source, prefix=Path("/opt/infrabadge-edges"), owner=0, run=subprocess.run):
    """Explicit future root preparation; no accounts, units, services or secrets."""
    value = lab.plan(value)
    if value["site"] != "home":
        raise ValueError("casa_core_only")
    validate_release(value, source, owner=owner)
    target = prefix / "releases" / value["release_sha"]
    if target.exists() or target.is_symlink():
        raise ValueError("existing_release_preserved")
    public_directory(prefix, owner)
    public_directory(prefix / "releases", owner)
    public_directory(target, owner)
    for name, file in release_files(source).items():
        destination = target / name
        for parent in reversed(destination.relative_to(target).parents):
            if parent != Path("."):
                public_directory(target / parent, owner)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "wb") as out:
            out.write(file.read_bytes())
            os.fchmod(out.fileno(), 0o644)
    fd = os.open(target / "source-manifest.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write((source / "source-manifest.json").read_bytes())
    validate_release(value, target, owner=owner)
    # Child-only umask: code/venv readable by the dedicated UID; secrets stay0600.
    run(
        [sys.executable, "-m", "venv", str(target / "venv")],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
        umask=0o022,
    )
    run(
        [
            str(target / "venv/bin/python"),
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--require-hashes",
            "--only-binary=:all:",
            "-r",
            str(target / "deploy/m32/native/requirements-runtime.lock"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
        umask=0o022,
    )
    checked(run, [str(target / "venv/bin/python"), "-m", "pip", "check"])
    return {
        "event": "casa_release_staged",
        "source_sha": value["release_sha"],
        "services_changed": False,
    }


def core_state(run):
    values = [
        checked(
            run,
            ["/usr/bin/systemctl", "show", unit, "--property=ActiveState,MainPID", "--no-pager"],
        )
        for unit in CORE_UNITS
    ]
    if any("ActiveState=active" not in v.splitlines() for v in values):
        raise ValueError("core_or_collector_not_active")
    return values[0]  # Collector oneshot/PID may advance normally; its timer must stay active.


def collector_reload_window(run, clock=time.monotonic, pause=time.sleep):
    """This host: local period30s, min_interval15s, OnActiveSec5s after reload."""
    until = clock() + 35
    while clock() < until:
        status = checked(
            run,
            [
                "/usr/bin/systemctl",
                "show",
                "infrabadge-m32-collector.service",
                "--property=ActiveState,Result",
                "--no-pager",
            ],
        ).splitlines()
        if "ActiveState=inactive" in status and "Result=success" in status:
            stamp = checked(
                run,
                [
                    "/usr/bin/busctl",
                    "--system",
                    "get-property",
                    "org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1/unit/infrabadge_2dm32_2dcollector_2eservice",
                    "org.freedesktop.systemd1.Unit",
                    "InactiveEnterTimestampMonotonic",
                ],
            ).split()
            if len(stamp) != 2 or stamp[0] != "t":
                raise ValueError("collector_numeric_timestamp_required")
            age = clock() - int(stamp[1]) / 1e6
            if 18 <= age <= 22:
                return age
        pause(0.2)
    raise ValueError("collector_reload_window_unavailable")


def validate_materials(bundle, value, run):
    from infrabadge_gateway.distributed.private import private_bytes, private_parent

    for name in MATERIALS:
        private_parent(bundle / name)
        raw = private_bytes(bundle / name, 131072)
        if name.endswith(".token"):
            import re

            if not re.fullmatch(rb"[A-Za-z0-9_-]{32,96}", raw.strip()):
                raise ValueError("credential_format")
    if (
        private_bytes(bundle / "edge.token").strip()
        == private_bytes(bundle / "probe.token").strip()
    ):
        raise ValueError("independent_roles_required")
    # Offline chain, validity and key pairing. Never reads a CA signing key.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(bundle / "server.pem", bundle / "server.key")
    checked(
        run,
        [
            "/usr/bin/openssl",
            "verify",
            "-CAfile",
            str(bundle / "edge-ca.pem"),
            str(bundle / "server.pem"),
        ],
    )
    decoded = ssl._ssl._test_decode_cert(str(bundle / "server.pem"))
    required = [("IP Address", "127.0.0.1")]
    try:
        ipaddress.IPv4Address(value["edge_hostname"])
        required.append(("IP Address", value["edge_hostname"]))
    except ValueError:
        required.append(("DNS", value["edge_hostname"]))
    if any(s not in decoded.get("subjectAltName", []) for s in required):
        raise ValueError("exact_loopback_and_lan_san_required")
    if ssl.cert_time_to_seconds(decoded["notAfter"]) - time.time() < 604800:
        raise ValueError("leaf_renewal_required")


def install_loopback(
    value,
    bundle,
    unit_root=Path("/etc/systemd/system"),
    config_root=Path("/etc"),
    run=subprocess.run,
    account=pwd.getpwnam,
    clock=lambda: time.clock_gettime(time.CLOCK_BOOTTIME),
):
    """Only used by the gated CLI after host/root/release checks. Tests use temp roots."""
    from infrabadge_gateway.distributed.private import private_bytes

    value = lab.plan(value)
    if value["site"] != "home":
        raise ValueError("casa_core_only")
    expected = lab.render(value, lab.ROOT / "deploy/permanent_edge", "loopback") | configs(value)
    # Reject an altered bundle before any user/file/service change.
    for name, text in expected.items():
        if private_bytes(bundle / name).decode() != text:
            raise ValueError("bundle_drift")
    units = {n: t for n, t in expected.items() if n.endswith((".service", ".timer"))}
    destination = config_root / "infrabadge-edge-home"
    if (
        destination.exists()
        or destination.is_symlink()
        or any((unit_root / n).exists() or (unit_root / n).is_symlink() for n in units)
    ):
        raise ValueError("existing_edge_preserved")
    try:
        account(value["service_user"])
    except KeyError:
        pass
    else:
        raise ValueError("existing_user_preserved")
    validate_materials(bundle, value, run)
    baseline = core_state(run)
    firewall = checked(run, ["/usr/sbin/nft", "-j", "list", "ruleset"])
    before_firewall = rollback.table_digest(json.loads(firewall))
    checked(
        run,
        [
            "/usr/sbin/useradd",
            "--system",
            "--user-group",
            "--no-create-home",
            "--shell",
            "/usr/sbin/nologin",
            value["service_user"],
        ],
    )
    user = account(value["service_user"])
    destination.mkdir(mode=0o700)
    os.chown(destination, user.pw_uid, user.pw_gid)
    for name in (*MATERIALS, "edge.json", "probe.json", "plan.json"):
        raw = private_bytes(bundle / name)
        fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        os.chown(destination / name, user.pw_uid, user.pw_gid)
    for name, text in units.items():
        fd = os.open(unit_root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as f:
            f.write(text)
    # No enable: a failed trial cannot restart itself on boot.
    reload_age = collector_reload_window(run)
    checked(run, ["/usr/bin/systemctl", "daemon-reload"])
    state = (
        Path("/run/infrabadge-edge-home")
        if config_root == Path("/etc")
        else config_root / "trial-state"
    )
    state.mkdir(mode=0o700)  # Existing state/consumed trial is never overwritten.
    armed = clock()
    plan = dict(
        schema_version=1,
        site="home",
        plan_id=os.urandom(16).hex(),
        boot_sha256=hashlib.sha256(
            Path("/proc/sys/kernel/random/boot_id").read_bytes()
        ).hexdigest(),
        armed_boottime=armed,
        deadline_boottime=armed + 1140,
        units_sha256={
            n: hashlib.sha256(t.encode()).hexdigest()
            for n, t in units.items()
            if "-rollback." not in n
        },
        table_sha256=None,
        units_previously_absent=True,
    )
    with os.fdopen(
        os.open(state / "rollback.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w"
    ) as f:
        json.dump(plan, f)
    checked(run, ["/usr/bin/systemctl", "start", "infrabadge-edge-home-rollback.timer"])
    if (
        checked(run, ["/usr/bin/systemctl", "is-active", "infrabadge-edge-home-rollback.timer"])
        != "active"
    ):
        raise ValueError("watchdog_not_active_no_listener")
    raw_deadline = checked(
        run,
        [
            "/usr/bin/busctl",
            "--system",
            "get-property",
            "org.freedesktop.systemd1",
            "/org/freedesktop/systemd1/unit/infrabadge_2dedge_2dhome_2drollback_2etimer",
            "org.freedesktop.systemd1.Timer",
            "NextElapseUSecMonotonic",
        ],
    ).split()
    if len(raw_deadline) != 2 or raw_deadline[0] != "t":
        raise ValueError("watchdog_numeric_deadline_required")
    next_us = int(raw_deadline[1])
    left = next_us / 1e6 - time.monotonic()
    if not 1080 <= left <= 1145:
        raise ValueError("watchdog_deadline_no_listener")
    try:
        checked(run, ["/usr/bin/systemctl", "start", "infrabadge-edge-home.service"])
        release = "/opt/infrabadge-edges/releases/" + value["release_sha"]
        checked(
            run,
            [
                "/usr/sbin/runuser",
                "-u",
                value["service_user"],
                "--",
                release + "/venv/bin/python",
                "-I",
                "-B",
                release + "/tools/permanent_edge/ib_edge_lab.py",
                "wait-tls",
                "--config",
                str(destination / "probe.json"),
            ],
            timeout=25,
        )
        checked(
            run,
            [
                "/usr/sbin/runuser",
                "-u",
                value["service_user"],
                "--",
                release + "/venv/bin/python",
                "-I",
                "-B",
                release + "/tools/permanent_edge/ib_edge_lab.py",
                "probe",
                "--config",
                str(destination / "probe.json"),
            ],
        )
        if core_state(run) != baseline:
            raise ValueError("core_state_changed")
        if (
            rollback.table_digest(
                json.loads(checked(run, ["/usr/sbin/nft", "-j", "list", "ruleset"]))
            )
            != before_firewall
        ):
            raise ValueError("firewall_changed")
    except Exception:
        checked(
            run,
            [
                "/usr/bin/systemctl",
                "stop",
                "infrabadge-edge-home-probe.timer",
                "infrabadge-edge-home-probe.service",
                "infrabadge-edge-home.service",
            ],
        )
        raise
    return {
        "event": "casa_loopback_trial",
        "https_probe": True,
        "core_unchanged": True,
        "firewall_unchanged": True,
        "watchdog_armed": True,
        "enabled": False,
        "collector_inactive_age_at_reload": round(reload_age, 3),
    }


def release_files(root):
    files = set(root.glob("gateway/infrabadge_gateway/**/*.py"))
    files.update(root.glob("tools/permanent_edge/*.py"))
    files.update(root.glob("deploy/permanent_edge/*.in"))
    files.update(
        (root / "gateway/requirements.lock", root / "deploy/m32/native/requirements-runtime.lock")
    )
    return {str(p.relative_to(root)): p for p in files}


def release_manifest(value, root=lab.ROOT, run=subprocess.run):
    # Export on the development checkout; the Raspberry does not need Git.
    if checked(run, ["git", "-C", str(root), "rev-parse", "HEAD"]) != value["release_sha"]:
        raise ValueError("checkout_revision")
    checked(run, ["git", "-C", str(root), "diff", "--exit-code", "HEAD", "--"])
    return {
        "schema_version": 1,
        "source_sha": value["release_sha"],
        "files": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in release_files(root).items()
        },
    }


def validate_release(value, root, owner=0):
    data = rollback.private(root / "source-manifest.json", owner=owner)
    files = release_files(root)
    if (
        set(data) != {"schema_version", "source_sha", "files"}
        or data["schema_version"] != 1
        or data["source_sha"] != value["release_sha"]
        or not files
        or set(data["files"]) != set(files)
        or "gateway/infrabadge_gateway/distributed/cli.py" not in files
        or "tools/permanent_edge/pilot.py" not in files
    ):
        raise ValueError("release_manifest")
    for name, path in files.items():
        for parent in path.parents:
            if parent == root.parent:
                break
            info = parent.stat()
            if info.st_uid != owner or info.st_mode & 0o022:
                raise ValueError("release_directory_writable")
        info = path.lstat()
        if (
            any(p.is_symlink() for p in (path, *path.parents))
            or info.st_uid != owner
            or info.st_mode & 0o022
            or hashlib.sha256(path.read_bytes()).hexdigest() != data["files"][name]
        ):
            raise ValueError("release_source_drift")


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("mode", choices=("prepare", "manifest", "stage-release", "install-loopback"))
    a.add_argument("--plan", type=Path, required=True)
    a.add_argument("--directory", type=Path, required=True)
    a.add_argument("--phase", choices=("loopback", "lan"), default="loopback")
    a.add_argument("--execute-authorized-loopback-install", action="store_true")
    a.add_argument("--execute-authorized-release-preparation", action="store_true")
    args = a.parse_args()
    try:
        value = lab.plan(lab.private_json(args.plan))
        if args.mode == "manifest":
            from infrabadge_gateway.distributed.private import private_parent

            private_parent(args.directory / "source-manifest.json")
            data = release_manifest(value)
            fd = os.open(
                args.directory / "source-manifest.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, sort_keys=True)
            result = {"event": "casa_source_manifest", "installed": False}
        elif args.mode == "prepare":
            result = prepare(value, args.directory, args.phase)
        elif args.mode == "stage-release":
            if (
                not args.execute_authorized_release_preparation
                or os.geteuid() != 0
                or socket.gethostname().split(".")[0] != "infrabadge-core"
            ):
                raise ValueError("specific_release_preparation_approval_required")
            result = stage_release(value, args.directory)
        else:
            if (
                not args.execute_authorized_loopback_install
                or os.geteuid() != 0
                or socket.gethostname().split(".")[0] != "infrabadge-core"
                or args.phase != "loopback"
            ):
                raise ValueError("specific_core_root_approval_required")
            from infrabadge_gateway.distributed.private import private_parent

            private_parent(args.directory / "plan.json")
            release = Path("/opt/infrabadge-edges/releases") / value["release_sha"]
            if release.is_symlink() or release.stat().st_uid != 0 or release.stat().st_mode & 0o022:
                raise ValueError("root_owned_pinned_release_required")
            validate_release(value, release)
            result = install_loopback(value, args.directory)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print('{"event":"casa_pilot","pass":false,"error":"manual_review_required"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
