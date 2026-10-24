"""Provider-neutral durable events. Only explicit HTTPS notification sends data."""

import http.client
import json
import re
import ssl
import uuid
from urllib.parse import urlsplit

MESSAGES = {
    "ok": "Certificate valid",
    "warning": "Certificate approaches expiry",
    "critical": "Certificate validity critically low",
    "expired": "Certificate expired",
    "validation_failed": "TLS validation failed; review required",
    "renewal_failed": "Renewal failed; review required",
    "recovered": "TLS validation or renewal recovered",
    "monitor_stale": "Certificate monitor has no recent successful execution",
}


def emit(state, component, kind, now):
    if kind not in MESSAGES or not re.fullmatch(r"[a-z0-9_-]{1,40}", component):
        raise ValueError("public_event_fields")
    previous = state.setdefault("statuses", {}).get(component)
    if previous == kind:
        return  # Stable condition: no duplicate or growing queue.
    state["statuses"][component] = kind
    if kind == "ok" and previous in (None, "ok"):
        return
    if kind == "ok":
        kind = "recovered"
    event = {
        "schema_version": 1,
        "event_id": uuid.uuid4().hex,
        "component": component,
        "kind": kind,
        "severity": "info"
        if kind == "recovered"
        else "warning"
        if kind == "warning"
        else "critical",
        "timestamp_utc": int(now),
        "description": MESSAGES[kind],
    }
    queue = state.setdefault("outbox", [])
    if len(queue) >= 128:
        raise ValueError("notification_outbox_full")
    queue.append({"event": event, "attempts": 0, "next_attempt": int(now), "delivered": False})


def send(config, event, token, connection_factory=http.client.HTTPSConnection):
    url = urlsplit(config["url"])
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.fragment
        or url.query
    ):
        raise ValueError("https_webhook_only")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        raise ValueError("webhook_credential")
    context = ssl.create_default_context(cafile=config["ca_file"])
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    connection = connection_factory(url.hostname, url.port or 443, context=context, timeout=5)
    try:
        connection.request(
            "POST",
            url.path or "/",
            json.dumps(event).encode(),
            {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "Idempotency-Key": event["event_id"],
            },
        )
        response = connection.getresponse()
        if not 200 <= response.status < 300 or len(response.read(4097)) > 4096:
            raise ValueError("webhook_rejected")  # No redirects, body/URL/token in errors.
    finally:
        connection.close()


def deliver(state, config, token, now, sender=send):
    """At-least-once; receiver must deduplicate event_id after ambiguous network failures."""
    delivered = failed = 0
    for item in state.get("outbox", []):
        if item["delivered"] or item["attempts"] >= 3 or item["next_attempt"] > now:
            continue
        if delivered + failed >= 4:
            break
        item["attempts"] += 1
        try:
            sender(config, item["event"], token)
            item["delivered"] = True
            delivered += 1
        except Exception:
            failed += 1
            item["next_attempt"] = int(now) + 60 * 2 ** (item["attempts"] - 1)
    # Keep undelivered/exhausted events for explicit review, bounded successful history.
    successes = [x for x in state.get("outbox", []) if x["delivered"]][-16:]
    state["outbox"] = [x for x in state.get("outbox", []) if not x["delivered"]] + successes
    return {
        "delivered": delivered,
        "failed": failed,
        "exhausted": sum(x["attempts"] >= 3 and not x["delivered"] for x in state["outbox"]),
    }
