"""Read-only CASA TLS expiry monitor and bounded Core TLS readiness. No HTTP/tokens."""

import argparse
import errno
import http.client
import json
import ssl
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ib_edge_lab as lab

DAY = 86400


def expiry_status(seconds):
    if seconds <= 0:
        return "expired"
    if seconds <= 7 * DAY:
        return "critical"
    if seconds <= 10 * DAY:
        return "warning"
    return "ok"


def certificates(directory, address, run=subprocess.run, now=time.time):
    """Verify leaf purpose/SAN/dates and both trust anchors; never load signing keys."""
    if address != lab.plan(lab.private_json(directory / "plan.json"))["lan_ipv4"]:
        raise ValueError("approved_address_required")
    result = run(
        [
            "/usr/bin/openssl",
            "verify",
            "-purpose",
            "sslserver",
            "-verify_ip",
            address,
            "-CAfile",
            str(directory / "edge-ca.pem"),
            str(directory / "server.pem"),
        ],
        check=True,
        capture_output=True,
        timeout=5,
    )
    if b"OK" not in result.stdout:
        raise ValueError("leaf_chain_invalid")
    remaining = []
    for name in ("server.pem", "edge-ca.pem", "core-ca.pem"):
        result = run(
            ["/usr/bin/openssl", "x509", "-in", str(directory / name), "-noout", "-enddate"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        line = result.stdout.strip()
        if not line.startswith("notAfter="):
            raise ValueError("certificate_expiry_unavailable")
        remaining.append(ssl.cert_time_to_seconds(line.removeprefix("notAfter=")) - now())
    minimum = min(remaining)
    return {
        "event": "edge_tls_expiry",
        "status": expiry_status(minimum),
        "minimum_days_remaining": round(minimum / DAY, 2),
        "remote_notification_configured": False,
    }


def core_ready(
    ca_file,
    run=subprocess.run,
    connection_factory=http.client.HTTPSConnection,
    clock=time.monotonic,
    pause=time.sleep,
    timeout=20,
):
    if not 0 < timeout <= 20:
        raise ValueError("bounded_core_readiness_required")
    if (
        run(
            ["/usr/bin/timedatectl", "show", "--property=NTPSynchronized", "--value"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout.strip()
        != "yes"
    ):
        raise ValueError("clock_not_synchronized")
    context = ssl.create_default_context(cafile=str(ca_file))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    start = clock()
    while clock() - start < timeout:
        connection = connection_factory(
            "127.0.0.1", 9443, context=context, timeout=min(1, timeout - (clock() - start))
        )
        try:
            connection.connect()  # Handshake only; do not issue HTTP or read credentials.
            return {"event": "edge_core_ready", "tls_verified": True, "http_sent": False}
        except ssl.SSLError:
            raise
        except OSError as error:
            if not isinstance(error, TimeoutError) and error.errno not in (
                errno.ECONNREFUSED,
                errno.ECONNRESET,
                errno.ETIMEDOUT,
            ):
                raise
        finally:
            connection.close()
        pause(min(0.2, max(0, timeout - (clock() - start))))
    raise TimeoutError("core_tls_readiness_deadline")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("monitor", "ready"))
    args = parser.parse_args()
    try:
        directory = Path("/etc/infrabadge-edge-home")
        plan = lab.plan(lab.private_json(directory / "plan.json"))
        if plan["site"] != "home":
            raise ValueError("casa_only")
        result = certificates(directory, plan["lan_ipv4"])
        print(json.dumps(result), flush=True)
        if args.mode == "ready":
            if result["status"] in ("critical", "expired"):
                raise ValueError("renewal_required_before_start")
            print(json.dumps(core_ready(directory / "core-ca.pem")), flush=True)
        return 0 if result["status"] == "ok" or args.mode == "ready" else 1
    except Exception:
        print(
            '{"event":"edge_tls_expiry","status":"error","error":"manual_review_required"}',
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
