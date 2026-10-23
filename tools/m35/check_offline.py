#!/usr/bin/env python3
"""Run regression without host sockets. Real TLS/socket tests stay CI/future-only."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED = (
    "gateway/tests/test_m35.py::test_v2_real_two_hop_tls",
    "gateway/tests/test_m3_observer.py::test_actual_upstream_tls_ca_hostname_dates",
    "gateway/tests/test_https.py::test_real_tls",
    "gateway/tests/test_m3_https.py::test_collector_real_verified_tls",
    "gateway/tests/test_phase_a.py::test_real_phase_a_client_with_explicit_ca",
    "gateway/tests/test_auto_diagnostic.py::test_generated_cert_variants_isolate_ca_san_and_dates_over_real_host_tls",
    "gateway/tests/test_m32_edge.py::test_actual_two_hop_tls_uses_explicit_ca_and_never_forwards_collector",
    "gateway/tests/test_m32_edge.py::test_upstream_certificate_failure_returns_unavailable_without_http",
    "gateway/tests/test_m32_native.py::test_two_inherited_tls_sockets_share_one_store_and_identity_scopes",
)


def no_network(event, _args):
    if event in ("socket.bind", "socket.connect", "socket.getaddrinfo"):
        raise RuntimeError("M3.5 offline-only: real network operation rejected")


if __name__ == "__main__":
    sys.addaudithook(no_network)
    print(
        "Offline regression: no host listeners or real network. Socket/TLS cases explicitly deselected."
    )
    raise SystemExit(
        pytest.main(["-c", str(ROOT / "pytest.ini"), *["--deselect=" + name for name in EXCLUDED]])
    )
