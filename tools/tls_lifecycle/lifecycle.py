"""Software-only CASA renewal engine. Host mutation requires the separate guarded CLI."""

import contextlib
import fcntl
import hashlib
import json
import os
import stat
import time
import uuid
from pathlib import Path

import notifications
import pki

SERVICE = "infrabadge-edge-home.service"
DAY = pki.DAY


def atomic(path, raw, owner=None):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if owner is not None:
            os.chown(temporary, owner[0], owner[1])
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def save(path, value):
    atomic(path, json.dumps(value, sort_keys=True, allow_nan=False).encode())


def load(path):
    def unique(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise ValueError("duplicate_json_key")
            value[k] = v
        return value

    return json.loads(pki.private(path, os.getuid()), object_pairs_hook=unique)


@contextlib.contextmanager
def locked(directory):
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("private_state_directory")
    fd = os.open(directory / "lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("lock_owner_mode")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def settings(value):
    fields = {
        "schema_version",
        "directory",
        "state_directory",
        "owner_uid",
        "owner_gid",
        "sans",
        "ca_sha256",
        "unit_sha256",
        "issuer_executable",
        "issuer_config",
        "warning_seconds",
        "critical_seconds",
        "renew_seconds",
        "lifetime_days",
        "monitor_max_age",
        "notification",
        "additional_certificates",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise ValueError("configuration_schema")
    for field in ("directory", "state_directory", "issuer_executable", "issuer_config"):
        if type(value[field]) is not str or not Path(value[field]).is_absolute():
            raise ValueError("absolute_path")
    for field in ("owner_uid", "owner_gid"):
        if type(value[field]) is not int or value[field] <= 0:
            raise ValueError("dedicated_edge_owner")
    for field in ("ca_sha256", "unit_sha256"):
        if (
            type(value[field]) is not str
            or len(value[field]) != 64
            or any(x not in "0123456789abcdef" for x in value[field])
        ):
            raise ValueError("pinned_digest")
    pki.san_names(value["sans"])
    for field in (
        "critical_seconds",
        "warning_seconds",
        "renew_seconds",
        "monitor_max_age",
        "lifetime_days",
    ):
        if type(value[field]) is not int:
            raise ValueError("integer_policy")
    if not (
        3600
        <= value["critical_seconds"]
        < value["warning_seconds"]
        <= value["renew_seconds"]
        <= 10 * DAY
        < value["lifetime_days"] * DAY
        <= 14 * DAY
        and 6 * 3600 <= value["monitor_max_age"] <= DAY
    ):
        raise ValueError("bounded_validity_policy")
    if (
        type(value["additional_certificates"]) is not list
        or len(value["additional_certificates"]) > 4
    ):
        raise ValueError("inventory_limit")
    for cert in value["additional_certificates"]:
        if set(cert) != {"component", "path", "owner_uid", "sha256"}:
            raise ValueError("inventory_schema")
        if cert["component"] in ("edge-casa", "edge-ca", "renewal", "monitor"):
            raise ValueError("reserved_component")
    notification = value["notification"]
    if notification is not None and (
        type(notification) is not dict or set(notification) != {"url", "ca_file", "token_file"}
    ):
        raise ValueError("notification_schema")
    return value


def paths(config):
    directory = Path(config["directory"])
    return directory / "server.pem", directory / "server.key", directory / "edge-ca.pem"


def clock_ok(state, now, synchronized):
    # Never issue/rotate or call HTTPS with unknown time; backward jumps fail closed.
    if (
        not synchronized
        or not 1767225600 <= now <= 4102444800
        or now < state.get("last_clock", 0) - 5
    ):
        raise ValueError("trusted_clock_required")
    state["last_clock"] = max(now, state.get("last_clock", 0))


def severity(remaining, config):
    if remaining <= 0:
        return "expired"
    if remaining <= config["critical_seconds"]:
        return "critical"
    if remaining <= config["warning_seconds"]:
        return "warning"
    return "ok"


def monitor(config, state, now, synchronized=True):
    clock_ok(state, now, synchronized)
    cert, _, ca = paths(config)
    observations = []
    items = [
        ("edge-casa", cert, config["owner_uid"], None),
        ("edge-ca", ca, config["owner_uid"], config["ca_sha256"]),
    ]
    items += [
        (x["component"], Path(x["path"]), x["owner_uid"], x["sha256"])
        for x in config["additional_certificates"]
    ]
    for component, path, owner, expected in items:
        try:
            pki.private(path, owner)
            if expected and pki.digest(path) != expected:
                raise ValueError("trust_anchor_drift")
            before, after = pki.dates(path)
            status = severity(after - now, config)
            if before > now:
                raise ValueError("certificate_not_yet_valid")
            if component == "edge-casa" and status != "expired":
                pki.private(ca, config["owner_uid"])
                if pki.digest(ca) != config["ca_sha256"]:
                    raise ValueError("ca_drift")
                pki.validate(cert, None, ca, config["sans"], now)
        except Exception:
            status = "validation_failed"
        notifications.emit(state, component, status, now)
        observations.append({"component": component, "status": status})
    state["last_monitor"] = int(now)
    notifications.emit(state, "monitor", "ok", now)
    return observations


def check_stale(config, state, now):
    if now - state.get("last_monitor", 0) > config["monitor_max_age"]:
        notifications.emit(state, "monitor", "monitor_stale", now)


def verify_public_runtime(config, unit_path):
    """Verifier boundary: never open, stat, resolve or hash the private key path."""
    cert, _, ca = paths(config)
    for path in (cert, ca):
        pki.private(path, config["owner_uid"])
    if any(p.stat().st_gid != config["owner_gid"] for p in (cert, ca)):
        raise ValueError("runtime_group_drift")
    if pki.digest(ca) != config["ca_sha256"] or pki.digest(unit_path) != config["unit_sha256"]:
        raise ValueError("runtime_configuration_drift")


def verify_runtime(config, unit_path):
    """Authorized renewer boundary: custody metadata and cryptographic pair check."""
    verify_public_runtime(config, unit_path)
    cert, key, _ = paths(config)
    pki.private(key, config["owner_uid"], read=False)
    if key.stat().st_gid != config["owner_gid"]:
        raise ValueError("runtime_group_drift")
    pki.matching_key(cert, key)


def candidate(config, folder, now, issue):
    """Only an explicit preapproved issuer receives a public CSR, never the Edge key."""
    _, _, ca = paths(config)
    key, request = pki.csr(folder, config["sans"])
    raw = issue(request.read_bytes())
    if type(raw) is not bytes or len(raw) > 16384 or raw.count(b"BEGIN CERTIFICATE") != 1:
        raise ValueError("issuer_response")
    cert = folder / "server.pem"
    atomic(cert, raw)
    checked_now = time.time()
    if abs(checked_now - now) > 60:
        raise ValueError("clock_changed_during_renewal")
    result = pki.validate(cert, key, ca, config["sans"], checked_now, minimum=7 * DAY + 60)
    if result["not_after"] - result["not_before"] > (config["lifetime_days"] * DAY + 300):
        raise ValueError("issuer_lifetime_exceeds_policy")
    return cert, key


def restore(config, transaction, host, now):
    """Idempotent recovery of this one pair only. Never overwrite unrelated drift."""
    if transaction["phase"] in ("committed", "rolled_back"):
        return transaction["phase"]
    if (
        transaction.get("config_sha256")
        != hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    ):
        raise ValueError("rollback_configuration_drift")
    cert, key, _ = paths(config)
    folder = Path(transaction["folder"])
    # Do not trust paths or ownership supplied by a corrupted journal.
    if folder.parent != Path(config["state_directory"]) or not folder.name.startswith("run-"):
        raise ValueError("transaction_scope")
    for path in (cert, key):
        name = path.name
        if pki.digest(path) not in (transaction["old"][name], transaction["new"][name]):
            raise ValueError("rollback_material_drift")
        backup = folder / (name + ".previous")
        pki.private(backup, os.getuid())
        if pki.digest(backup) != transaction["old"][name]:
            raise ValueError("backup_drift")
    host.check()
    host.stop()
    for path in (cert, key):
        atomic(
            path,
            (folder / (path.name + ".previous")).read_bytes(),
            (config["owner_uid"], config["owner_gid"]),
        )
    # Restoring an expired pair must not restart an unusable listener.
    try:
        pki.validate(cert, key, paths(config)[2], config["sans"], now)
        host.start()
        host.probe()
    except Exception:
        host.stop()
        transaction["phase"] = "recovery_failed"
        save(folder / "transaction.json", transaction)
        raise
    transaction["phase"] = "rolled_back"
    save(folder / "transaction.json", transaction)
    return "rolled_back"


def renew(config, state, now, host, issue, synchronized=True):
    clock_ok(state, now, synchronized)
    if state.get("pending"):
        raise ValueError("unfinished_transaction_requires_recovery")
    if state.get("renew_attempts", 0) >= 3 or now < state.get("renew_next", 0):
        return "backoff_or_review"
    cert, key, _ = paths(config)
    host.check()
    verify_runtime(config, host.unit_path)
    # Inspect expiry first: expired leaves can still be renewed against the pinned valid CA.
    before, after = pki.dates(cert)
    if before > now:
        raise ValueError("leaf_clock_skew")
    if after - now > config["renew_seconds"]:
        return "not_due"
    if not host.active():
        raise ValueError("edge_must_be_active")
    folder = Path(config["state_directory"]) / ("run-" + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    state["renew_attempts"] = state.get("renew_attempts", 0) + 1
    state["renew_next"] = int(now) + 3600 * 2 ** (state["renew_attempts"] - 1)
    save(Path(config["state_directory"]) / "state.json", state)
    transaction = None
    try:
        new_cert, new_key = candidate(config, folder, now, issue)
        # No interruption until issuance, all checks, durable backup and independent guard.
        verify_runtime(config, host.unit_path)
        for path in (cert, key):
            atomic(folder / (path.name + ".previous"), pki.private(path, config["owner_uid"]))
        transaction = {
            "phase": "prepared",
            "config_sha256": hashlib.sha256(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest(),
            "folder": str(folder),
            "old": {p.name: pki.digest(p) for p in (cert, key)},
            "new": {p.name: pki.digest(p) for p in (new_cert, new_key)},
        }
        save(folder / "transaction.json", transaction)
        state["pending"] = str(folder)
        save(Path(config["state_directory"]) / "state.json", state)
        host.arm()  # Must verify a numeric independent deadline before stop.
        host.check()
        transaction["phase"] = "stopping"
        save(folder / "transaction.json", transaction)
        host.stop()
        transaction["phase"] = "stopped"
        save(folder / "transaction.json", transaction)
        for path, source in ((cert, new_cert), (key, new_key)):
            atomic(path, source.read_bytes(), (config["owner_uid"], config["owner_gid"]))
        transaction["phase"] = "installed"
        save(folder / "transaction.json", transaction)
        host.start()
        host.probe()
        transaction["phase"] = "committed"
        save(folder / "transaction.json", transaction)
        state.pop("pending", None)
        state["renew_attempts"] = 0
        state["renew_next"] = 0
        notifications.emit(state, "renewal", "recovered", now)
        save(Path(config["state_directory"]) / "state.json", state)
        host.disarm()
        return "renewed"
    except Exception:
        if transaction and transaction["phase"] == "committed":
            # Material already verified/committed: a guard cleanup error must never undo it.
            return "renewed_guard_cleanup_pending"
        notifications.emit(state, "renewal", "renewal_failed", now)
        try:
            if transaction:
                if transaction["phase"] != "prepared":
                    restore(config, transaction, host, time.time())
                state.pop("pending", None)
        finally:
            save(Path(config["state_directory"]) / "state.json", state)
        if transaction:
            host.disarm()
        raise
