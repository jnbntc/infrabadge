"""One bounded HTTPS POST. No proxy environment, redirect, subprocess or retry."""

import contextlib
import http.client
import json
import re
import signal
import ssl
from urllib.parse import urlsplit

from .runtime import private_bytes


@contextlib.contextmanager
def deadline(seconds):
    # Fedora/Linux oneshot main thread: includes blocking DNS in the budget.
    # The enclosing systemd TimeoutStartSec is an additional process boundary.
    previous = signal.getsignal(signal.SIGALRM)
    timer = signal.getitimer(signal.ITIMER_REAL)
    if timer[0]:
        raise ValueError("existing_alarm")

    def expired(_number, _frame):
        raise TimeoutError("transport_deadline")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def submit(config, token_file, metrics):
    token = private_bytes(token_file, 128).decode("ascii").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,96}", token):
        raise ValueError("collector_credential_format")
    body = json.dumps(metrics, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(body) > 8192:
        raise ValueError("metrics_size")
    url = urlsplit(config["gateway_url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("verified_https_required")
    context = ssl.create_default_context(cafile=config["ca_file"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = http.client.HTTPSConnection(
        url.hostname, url.port or 443, timeout=config["timeout_seconds"], context=context
    )
    try:
        with deadline(config["timeout_seconds"]):
            connection.request(
                "POST",
                "/api/v1/collectors/" + config["node_id"] + "/metrics",
                body,
                {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            content = response.read(1025)
            if len(content) > 1024:
                raise ValueError("gateway_response_size")
            if response.status != 202:
                raise ValueError("gateway_rejected")  # Never log response/error bodies.
            if json.loads(content) != {"accepted": True}:
                raise ValueError("gateway_ack")
    finally:
        connection.close()
