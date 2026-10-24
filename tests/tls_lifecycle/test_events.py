"""Remote output is mocked or bound to loopback; no real message is sent."""

import http.server
import json
import ssl
import threading
import time

import notifications
import pytest

from tests.tls_lifecycle.test_lifecycle import lab  # noqa: F401


@pytest.mark.parametrize(
    "kind",
    [
        "warning",
        "critical",
        "expired",
        "validation_failed",
        "renewal_failed",
        "recovered",
        "monitor_stale",
    ],
)
def test_deduplication_recovery_public_envelope(kind):
    state = {}
    notifications.emit(state, "edge-casa", kind, 1800000000)
    notifications.emit(state, "edge-casa", kind, 1800000001)
    assert len(state["outbox"]) == 1
    event = state["outbox"][0]["event"]
    assert event["component"] == "edge-casa"
    assert set(event) == {
        "schema_version",
        "event_id",
        "component",
        "kind",
        "severity",
        "timestamp_utc",
        "description",
    }
    notifications.emit(state, "edge-casa", "ok", 1800000002)
    assert state["outbox"][-1]["event"]["kind"] == "recovered"
    notifications.emit(state, "edge-casa", "ok", 1800000003)
    assert len(state["outbox"]) == 2


def test_provider_failure_bounded_backoff_and_recovery():
    state = {}
    notifications.emit(state, "edge-casa", "critical", 1800000000)
    ids = []

    def failure(_config, event, _token):
        ids.append(event["event_id"])
        raise TimeoutError("opaque remote failure")

    for now in (1800000000, 1800000060, 1800000180, 1800001000):
        notifications.deliver(state, {}, "private", now, failure)
    assert len(ids) == 3 and len(set(ids)) == 1
    assert state["outbox"][0]["attempts"] == 3
    notifications.emit(state, "edge-casa", "ok", 1800002000)
    result = notifications.deliver(state, {}, "private", 1800002000, lambda *_: None)
    assert result == {"delivered": 1, "failed": 0, "exhausted": 1}


def test_idempotency_after_success():
    state = {}
    notifications.emit(state, "edge-casa", "warning", 1800000000)
    calls = []
    for _ in range(2):
        notifications.deliver(state, {}, "private", 1800000000, lambda *x: calls.append(x))
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "https://user:secret@localhost/x",
        "https://localhost/x?secret=bad",
        "https://localhost/x#frag",
    ],
)
def test_webhook_no_plaintext_or_credentials_in_url(url):
    with pytest.raises(ValueError, match="https"):
        notifications.send({"url": url}, {}, "x" * 40)


def test_real_https_authenticated_webhook_and_rejection(lab):  # noqa: F811
    config, _, _, _ = lab
    directory = config["directory"]
    received = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.headers["Authorization"] == "Bearer " + "x" * 40
            assert self.headers["Idempotency-Key"] == "synthetic-event"
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(204 if self.path == "/hook" else 302)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(directory + "/server.pem", directory + "/server.key")
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    event = {"event_id": "synthetic-event", "timestamp_utc": int(time.time())}
    webhook = {
        "url": f"https://127.0.0.1:{server.server_port}/hook",
        "ca_file": directory + "/edge-ca.pem",
    }
    try:
        notifications.send(webhook, event, "x" * 40)
        assert received == [event]
        webhook["url"] = webhook["url"].replace("/hook", "/redirect")
        with pytest.raises(ValueError, match="webhook_rejected"):
            notifications.send(webhook, event, "x" * 40)
        webhook["url"] = webhook["url"].replace("127.0.0.1", "localhost")
        with pytest.raises(ssl.SSLCertVerificationError):
            notifications.send(webhook, event, "x" * 40)
    finally:
        server.shutdown()
        server.server_close()
