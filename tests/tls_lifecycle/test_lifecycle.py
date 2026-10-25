"""Disposable PKI and fake host; no production certificates/services are accessed."""

import datetime as dt
import http.client
import http.server
import os
import ssl
import threading
import time
from pathlib import Path

import issuer
import lifecycle as engine
import pki
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

DAY = pki.DAY


def authority(folder, days=90):
    folder.mkdir(mode=0o700)
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Disposable TLS test CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    engine.atomic(folder / "ca.pem", cert.public_bytes(serialization.Encoding.PEM))
    engine.atomic(
        folder / "ca.key",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    return folder / "ca.pem", folder / "ca.key"


@pytest.fixture
def lab(tmp_path):
    tmp_path.chmod(0o700)
    ca, signing_key = authority(tmp_path / "signer")
    edge = tmp_path / "edge"
    edge.mkdir(mode=0o700)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    ca_copy = edge / "edge-ca.pem"
    engine.atomic(ca_copy, ca.read_bytes())
    unit = tmp_path / "edge.service"
    unit.write_text("synthetic unit\n")
    signer = {
        "ca_file": str(ca),
        "ca_key_file": str(signing_key),
        "ca_sha256": pki.digest(ca),
        "sans": ["127.0.0.1"],
        "lifetime_days": 14,
    }
    config = engine.settings(
        {
            "schema_version": 1,
            "directory": str(edge),
            "state_directory": str(state),
            "owner_uid": os.getuid(),
            "owner_gid": os.getgid(),
            "sans": ["127.0.0.1"],
            "ca_sha256": pki.digest(ca_copy),
            "unit_sha256": pki.digest(unit),
            "issuer_executable": "/unused/issuer",
            "issuer_config": "/unused/private.json",
            "warning_seconds": 7 * DAY,
            "critical_seconds": 2 * DAY,
            "renew_seconds": 10 * DAY,
            "lifetime_days": 14,
            "monitor_max_age": 13 * 3600,
            "notification": None,
            "additional_certificates": [],
        }
    )
    request_dir = tmp_path / "initial"
    request_dir.mkdir(mode=0o700)
    key, request = pki.csr(request_dir, config["sans"])
    leaf = issuer.sign(signer, request.read_bytes(), time.time())
    engine.atomic(edge / "server.pem", leaf)
    engine.atomic(edge / "server.key", key.read_bytes())
    return config, signer, unit, tmp_path


class Host:
    def __init__(self, unit, fail=None):
        self.unit_path, self.fail = unit, fail
        self.calls = []
        self.running = True
        self.starts = self.probes = 0

    def check(self):
        self.calls.append("check")

    def active(self):
        return self.running

    def arm(self):
        self.calls.append("arm_verified")
        if self.fail == "arm":
            raise RuntimeError("guard unavailable")

    def disarm(self):
        self.calls.append("disarm")

    def stop(self):
        self.calls.append("stop")
        self.running = False

    def start(self):
        self.calls.append("start")
        self.starts += 1
        if self.fail == "start" and self.starts == 1:
            raise RuntimeError("start failure")
        self.running = True

    def probe(self):
        self.calls.append("probe")
        self.probes += 1
        if self.fail == "probe" and self.probes == 1:
            raise RuntimeError("postcheck failure")


def due(lab):
    config, signer, unit, root = lab
    # Initial disposable leaf shortened to nine days without altering any trust anchor.
    cert, key, ca = engine.paths(config)
    original = x509.load_pem_x509_certificate(cert.read_bytes())
    signing = serialization.load_pem_private_key(Path(signer["ca_key_file"]).read_bytes(), None)
    builder = (
        x509.CertificateBuilder()
        .subject_name(original.subject)
        .issuer_name(original.issuer)
        .public_key(original.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1))
        .not_valid_after(dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=9))
    )
    for extension in original.extensions:
        builder = builder.add_extension(extension.value, extension.critical)
    engine.atomic(
        cert, builder.sign(signing, hashes.SHA256()).public_bytes(serialization.Encoding.PEM)
    )
    return config, signer, unit, root


def test_fresh_idempotent_no_issuer_or_interruption(lab):
    config, _, unit, _ = lab
    host = Host(unit)

    def never(_):
        pytest.fail("fresh certificate must not be issued")

    assert engine.renew(config, {}, time.time(), host, never) == "not_due"
    assert "stop" not in host.calls


@pytest.mark.parametrize("failure", [None, "issue", "start", "probe", "arm", "install"])
def test_transaction_success_failure_and_rollback(lab, monkeypatch, failure):
    config, signer, unit, _ = due(lab)
    host, state = Host(unit, failure), {}
    before = {p.name: p.read_bytes() for p in engine.paths(config)[:2]}

    def issue(csr):
        if failure == "issue":
            raise RuntimeError("emission failed")
        return issuer.sign(signer, csr, time.time())

    atomic = engine.atomic
    failed_once = [False]

    def broken_atomic(path, raw, owner=None):
        if failure == "install" and owner and not failed_once[0]:
            failed_once[0] = True
            raise OSError("installation failed")
        return atomic(path, raw, owner)

    monkeypatch.setattr(engine, "atomic", broken_atomic)
    if failure:
        with pytest.raises((RuntimeError, OSError)):
            engine.renew(config, state, time.time(), host, issue)
        assert {p.name: p.read_bytes() for p in engine.paths(config)[:2]} == before
        if failure in ("issue", "arm"):
            assert "stop" not in host.calls
        else:
            assert host.running
    else:
        assert engine.renew(config, state, time.time(), host, issue) == "renewed"
        assert host.calls.index("arm_verified") < host.calls.index("stop")
        assert host.calls[-1] == "disarm"
        assert engine.paths(config)[0].read_bytes() != before["server.pem"]
        assert engine.renew(config, state, time.time(), host, issue) == "not_due"
    assert not state.get("pending")
    assert engine.paths(config)[2].read_bytes() == Path(signer["ca_file"]).read_bytes()
    assert list(Path(config["state_directory"]).glob("run-*/server.key*")) or failure == "issue"


@pytest.mark.parametrize("change", ["ca", "san", "key", "permissions", "unit", "future", "expired"])
def test_validation_rejects_untrusted_material(lab, change):
    config, signer, unit, root = lab
    cert, key, ca = engine.paths(config)
    now = time.time()
    if change == "ca":
        other, _ = authority(root / "other")
        engine.atomic(ca, other.read_bytes())
    elif change == "san":
        config["sans"] = ["wrong.invalid"]
    elif change == "key":
        folder = root / "wrongkey"
        folder.mkdir(mode=0o700)
        wrong, _ = pki.csr(folder, ["127.0.0.1"])
        engine.atomic(key, wrong.read_bytes())
    elif change == "permissions":
        key.chmod(0o644)
    elif change == "unit":
        unit.write_text("drift")
    elif change == "future":
        now += 100 * DAY
    else:
        now -= 2 * DAY
    with pytest.raises(ValueError):
        engine.verify_runtime(config, unit)
        pki.validate(cert, key, ca, config["sans"], now)


@pytest.mark.parametrize(
    "left,status",
    [
        (20 * DAY, "ok"),
        (7 * DAY, "warning"),
        (2 * DAY, "critical"),
        (0, "expired"),
        (-DAY, "expired"),
    ],
)
def test_expiry_boundaries(lab, left, status):
    assert engine.severity(left, lab[0]) == status


@pytest.mark.parametrize("days", [11, 14, 30, 365])
def test_inventory_distinct_lifetimes_and_staleness(lab, days):
    config, _, _, root = lab
    public, _ = authority(root / "duration", days)
    config["additional_certificates"] = [
        {
            "component": "core-ca",
            "path": str(public),
            "owner_uid": os.getuid(),
            "sha256": pki.digest(public),
        }
    ]
    state = {}
    results = engine.monitor(config, state, time.time())
    assert all(x["status"] == "ok" for x in results)
    engine.check_stale(config, state, time.time() + 14 * 3600)
    assert state["outbox"][-1]["event"]["kind"] == "monitor_stale"


@pytest.mark.parametrize("now,sync", [(0, True), (time.time(), False)])
def test_untrusted_clock_never_issues(lab, now, sync):
    config, _, unit, _ = lab
    host = Host(unit)
    with pytest.raises(ValueError, match="clock"):
        engine.renew(config, {}, now, host, lambda _: pytest.fail("no issue"), synchronized=sync)
    assert not host.calls


def test_backward_clock(lab):
    with pytest.raises(ValueError, match="clock"):
        engine.monitor(lab[0], {"last_clock": time.time() + 600}, time.time())


def test_lock_exclusion_and_wrong_state_mode(lab):
    directory = Path(lab[0]["state_directory"])
    with engine.locked(directory), pytest.raises(BlockingIOError), engine.locked(directory):
        pass
    directory.chmod(0o755)
    with pytest.raises(ValueError):
        with engine.locked(directory):
            pass


def test_backoff_and_pending_recovery(lab):
    config, _, unit, _ = due(lab)
    host = Host(unit)
    for state in ({"renew_attempts": 3}, {"renew_next": time.time() + 600}):
        assert engine.renew(config, state, time.time(), host, lambda _: None) == "backoff_or_review"
    with pytest.raises(ValueError, match="unfinished"):
        engine.renew(config, {"pending": "private"}, time.time(), host, lambda _: None)


def test_real_local_tls_activation(lab):
    config, signer, unit, _ = due(lab)
    cert, key, ca = engine.paths(config)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer synthetic-probe"
            self.send_response(304 if self.headers.get("If-None-Match") == '"fixture"' else 200)
            self.send_header("ETag", '"fixture"')
            self.end_headers()

        def log_message(self, *args):
            pass

    class TLSHost(Host):
        server = None

        def stop(self):
            super().stop()
            if self.server:
                self.server.shutdown()
                self.server.server_close()
                self.server = None

        def start(self):
            super().start()
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
            threading.Thread(target=self.server.serve_forever, daemon=True).start()

        def probe(self):
            super().probe()
            context = ssl.create_default_context(cafile=ca)
            for tag, status in ((None, 200), ('"fixture"', 304)):
                client = http.client.HTTPSConnection(
                    "127.0.0.1", self.server.server_port, context=context
                )
                headers = {"Authorization": "Bearer synthetic-probe"}
                if tag:
                    headers["If-None-Match"] = tag
                client.request("GET", "/fixture", headers=headers)
                response = client.getresponse()
                assert response.status == status
                response.read()
                client.close()

    host = TLSHost(unit)
    try:
        assert (
            engine.renew(
                config, {}, time.time(), host, lambda csr: issuer.sign(signer, csr, time.time())
            )
            == "renewed"
        )
    finally:
        host.stop()
    assert not any("core" in call for call in host.calls)


def test_crash_between_pair_replacements_independent_recovery(lab, monkeypatch):
    config, signer, unit, _ = due(lab)
    host, state = Host(unit), {}
    cert, key, _ = engine.paths(config)
    before = cert.read_bytes(), key.read_bytes()
    atomic = engine.atomic

    def crash(path, raw, owner=None):
        if path == key and owner:
            raise KeyboardInterrupt("simulated power/process loss")
        return atomic(path, raw, owner)

    monkeypatch.setattr(engine, "atomic", crash)
    with pytest.raises(KeyboardInterrupt):
        engine.renew(
            config, state, time.time(), host, lambda csr: issuer.sign(signer, csr, time.time())
        )
    assert "disarm" not in host.calls and not host.running
    assert cert.read_bytes() != before[0] and key.read_bytes() == before[1]
    monkeypatch.setattr(engine, "atomic", atomic)
    transaction = engine.load(Path(state["pending"]) / "transaction.json")
    assert engine.restore(config, transaction, host, time.time()) == "rolled_back"
    assert (cert.read_bytes(), key.read_bytes()) == before and host.running
    assert engine.restore(config, transaction, host, time.time()) == "rolled_back"


def test_rollback_refuses_unrelated_drift(lab, monkeypatch):
    config, signer, unit, _ = due(lab)
    host, state = Host(unit), {}

    def crash():
        raise KeyboardInterrupt()

    monkeypatch.setattr(host, "start", crash)
    with pytest.raises(KeyboardInterrupt):
        engine.renew(
            config, state, time.time(), host, lambda csr: issuer.sign(signer, csr, time.time())
        )
    cert = engine.paths(config)[0]
    engine.atomic(cert, b"unrelated material")
    transaction = engine.load(Path(state["pending"]) / "transaction.json")
    with pytest.raises(ValueError, match="drift"):
        engine.restore(config, transaction, host, time.time())
    assert cert.read_bytes() == b"unrelated material"


@pytest.mark.parametrize("change", ["ca_digest", "san", "ca_expiry", "csr", "validity"])
def test_issuer_rejections(lab, change):
    config, signer, _, root = lab
    folder = root / "rejected"
    folder.mkdir(mode=0o700)
    _, request = pki.csr(folder, config["sans"])
    raw = request.read_bytes()
    if change == "ca_digest":
        signer["ca_sha256"] = "0" * 64
    elif change == "san":
        signer["sans"] = ["wrong.invalid"]
    elif change == "ca_expiry":
        ca, key = authority(root / "short-ca", 5)
        signer.update(ca_file=str(ca), ca_key_file=str(key), ca_sha256=pki.digest(ca))
    elif change == "csr":
        raw = b"invalid public request"
    else:
        signer["lifetime_days"] = 365
    with pytest.raises(ValueError):
        issuer.sign(signer, raw, time.time())


@pytest.mark.parametrize(
    "offset,status", [(8 * DAY, "warning"), (12 * DAY, "critical"), (15 * DAY, "expired")]
)
def test_monitor_real_certificate_dates(lab, offset, status):
    config = lab[0]
    result = engine.monitor(config, {}, time.time() + offset)
    assert result[0] == {"component": "edge-casa", "status": status}
    assert result[1]["status"] == "ok"


def test_success_not_rolled_back_if_guard_cleanup_fails(lab, monkeypatch):
    config, signer, unit, _ = due(lab)
    host, state = Host(unit), {}

    def failure():
        raise OSError("cleanup unavailable")

    monkeypatch.setattr(host, "disarm", failure)
    result = engine.renew(
        config, state, time.time(), host, lambda csr: issuer.sign(signer, csr, time.time())
    )
    assert result == "renewed_guard_cleanup_pending"
    assert not state.get("pending") and host.running
    assert host.calls.count("stop") == 1


def test_crash_recovery_rejects_configuration_drift(lab, monkeypatch):
    config, signer, unit, _ = due(lab)
    host, state = Host(unit), {}

    def crash():
        raise KeyboardInterrupt()

    monkeypatch.setattr(host, "start", crash)
    with pytest.raises(KeyboardInterrupt):
        engine.renew(
            config, state, time.time(), host, lambda csr: issuer.sign(signer, csr, time.time())
        )
    transaction = engine.load(Path(state["pending"]) / "transaction.json")
    config["sans"].append("wrong.invalid")
    with pytest.raises(ValueError, match="configuration_drift"):
        engine.restore(config, transaction, host, time.time())


def test_custodian_rejects_mismatched_active_key_before_interruption(lab):
    config, signer, unit, root = due(lab)
    other = root / "other-key"
    other.mkdir(mode=0o700)
    wrong, _ = pki.csr(other, config["sans"])
    engine.atomic(engine.paths(config)[1], wrong.read_bytes())
    host = Host(unit)
    with pytest.raises(ValueError, match="key_mismatch"):
        engine.renew(
            config, {}, time.time(), host, lambda csr: issuer.sign(signer, csr, time.time())
        )
    assert "stop" not in host.calls and "arm_verified" not in host.calls


def test_public_tls_verification_works_with_key_unreadable(lab, monkeypatch):
    import importlib.util
    from types import SimpleNamespace

    config, _, unit, root = lab
    cert, key, ca = engine.paths(config)
    spec = importlib.util.spec_from_file_location(
        "tls_protected_probe", Path(__file__).resolve().parents[2] / "tools/tls_lifecycle/cli.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)  # Authorized Edge loads its key before sandbox proof.
    key.chmod(0)
    with pytest.raises(PermissionError):
        key.read_bytes()
    server = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    probe = root / "probe.json"
    engine.save(probe, {"url": "https://127.0.0.1:8443", "ca_file": str(ca)})
    engine.save(root / "runtime.json", {"probe_config_sha256": pki.digest(probe)})
    monkeypatch.setattr(cli, "CONFIG", root / "config.json")
    monkeypatch.setattr(cli, "PROBE", probe)
    monkeypatch.setattr(cli, "UNIT", unit)
    monkeypatch.setattr(cli.Host, "check", lambda self: None)
    real_connection = http.client.HTTPSConnection
    commands = []

    def local_connection(host, _port, **kwargs):
        return real_connection(host, server.server_port, **kwargs)

    monkeypatch.setattr(
        cli, "http", SimpleNamespace(client=SimpleNamespace(HTTPSConnection=local_connection))
    )
    monkeypatch.setattr(pki, "command", lambda args, **kwargs: commands.append(args))
    try:
        cli.Host(
            config
        ).probe()  # Real verified handshake + served-leaf pin; API subprocess mocked.
        assert commands[0][0] == "/usr/sbin/runuser"
        assert not any(str(key) in args for args in commands)
    finally:
        server.shutdown()
        server.server_close()
        key.chmod(0o600)
