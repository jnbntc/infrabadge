"""Private bounded aggregate telemetry; no headers, IDs, addresses or payloads."""

import threading
import time

from .lan_policy import write_private

EVENTS = frozenset(
    (
        "gateway_started",
        "collector_accepted",
        "device_query",
        "auth_rejected",
        "edge_rejected",
        "rate_limited",
        "network_unavailable",
        "response_delivered",
        "snapshot_built",
    )
)


class Telemetry:
    def __init__(self, path=None, clock=time.time):
        self.lock = threading.Lock()
        self.path = path
        self.clock = clock
        self.state = dict(
            schema_version=1,
            counts={event: 0 for event in sorted(EVENTS)},
            telemetry_write_errors=0,
        )

    def emit(self, event, **values):
        if event not in EVENTS or any(
            key not in ("collected_at", "ttl_seconds", "state", "control") for key in values
        ):
            raise ValueError("telemetry_fields")
        for key, value in values.items():
            if key in ("collected_at", "ttl_seconds") and (type(value) is not int or value < 0):
                raise ValueError("telemetry_number")
            if key == "state" and value not in (
                "HEALTHY",
                "WARNING",
                "CRITICAL",
                "UNKNOWN",
                "OFFLINE",
            ):
                raise ValueError("telemetry_state")
            if key == "control" and value not in ("fresh", "stale", "absent"):
                raise ValueError("telemetry_control")
        with self.lock:
            now = int(self.clock())
            self.state["counts"][event] = min(2**63 - 1, self.state["counts"][event] + 1)
            self.state["last_" + event + "_at"] = now
            if event == "collector_accepted":
                self.state["last_collected_at"] = values["collected_at"]
                self.state["sample_ttl_seconds"] = values["ttl_seconds"]
            if "state" in values:
                self.state["last_state"] = values["state"]
            if "control" in values:
                self.state["last_control"] = values["control"]
            if self.path:
                try:
                    write_private(self.path, self.state)
                except (OSError, ValueError):
                    self.state["telemetry_write_errors"] = min(
                        2**63 - 1, self.state["telemetry_write_errors"] + 1
                    )


def view(state, now):
    """A file is evidence of past events, never proof that a process is alive."""
    counts = state.get("counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != EVENTS
        or any(type(v) is not int or not 0 <= v <= 2**63 - 1 for v in counts.values())
        or type(state.get("telemetry_write_errors")) is not int
    ):
        raise ValueError("invalid_private_telemetry")
    sampled = state.get("last_collected_at")
    age = now - sampled if type(sampled) is int and now >= sampled else None
    queried = state.get("last_device_query_at")
    return dict(
        process_liveness="not_proven_by_file",
        collector_sample_age_seconds=age,
        sample_fresh=age is not None and age < state.get("sample_ttl_seconds", 0),
        authenticated_query_age_seconds=now - queried
        if type(queried) is int and now >= queried
        else None,
        attribution="configured_credential_not_hardware_attestation",
        counts=state["counts"],
        telemetry_write_errors=state["telemetry_write_errors"],
    )
