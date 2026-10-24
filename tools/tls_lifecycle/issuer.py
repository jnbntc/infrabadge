#!/usr/bin/python3 -I
"""Optional isolated local signer. Never installed automatically; CSR stdin, leaf stdout.

Requires explicit approval to place an existing CA signing key in a separate
root-only signer directory. It NEVER creates or replaces a CA/trust store.
"""

import argparse
import math
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lifecycle
import pki


def sign(config, csr, now):
    fields = {"ca_file", "ca_key_file", "ca_sha256", "sans", "lifetime_days"}
    if type(config) is not dict or set(config) != fields:
        raise ValueError("issuer_schema")
    if type(config["lifetime_days"]) is not int or not 11 <= config["lifetime_days"] <= 14:
        raise ValueError("issuer_validity_policy")
    for name in ("ca_file", "ca_key_file"):
        pki.private(config[name], os.getuid(), read=name != "ca_key_file")
    if pki.digest(config["ca_file"]) != config["ca_sha256"]:
        raise ValueError("signer_ca_drift")
    before, after = pki.dates(config["ca_file"])
    if not before <= now < after:
        raise ValueError("signer_ca_dates")
    days = min(config["lifetime_days"], math.floor((after - now - 300) / pki.DAY))
    if days < 11:
        raise ValueError("ca_requires_separate_approval")
    if len(csr) > 16384 or csr.count(b"BEGIN CERTIFICATE REQUEST") != 1:
        raise ValueError("csr_limit")
    with tempfile.TemporaryDirectory(prefix="ib-signer-") as temporary:
        folder = Path(temporary)
        folder.chmod(0o700)
        request, cert, extensions = (
            folder / name for name in ("request.pem", "leaf.pem", "ext.cnf")
        )
        lifecycle.atomic(request, csr)
        pki.command(["/usr/bin/openssl", "req", "-in", str(request), "-verify", "-noout"])
        text = pki.command(
            ["/usr/bin/openssl", "req", "-in", str(request), "-noout", "-text"]
        ).decode()
        # Issuer accepts only the configured SAN set; certificate extensions are NOT copied from CSR.
        marker = "X509v3 Subject Alternative Name:"
        if text.count(marker) != 1:
            raise ValueError("csr_san")
        names = (
            text.split(marker, 1)[1]
            .splitlines()[1]
            .strip()
            .replace("IP Address:", "IP:")
            .split(", ")
        )
        if sorted(names) != sorted(pki.san_names(config["sans"])):
            raise ValueError("csr_scope")
        lifecycle.atomic(
            extensions,
            (
                "basicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n"
                "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n"
                "subjectAltName=" + ",".join(pki.san_names(config["sans"])) + "\n"
            ).encode(),
        )
        pki.command(
            [
                "/usr/bin/openssl",
                "x509",
                "-req",
                "-in",
                str(request),
                "-out",
                str(cert),
                "-CA",
                config["ca_file"],
                "-CAkey",
                config["ca_key_file"],
                "-set_serial",
                hex(secrets.randbits(159) or 1),
                "-days",
                str(days),
                "-sha256",
                "-extfile",
                str(extensions),
                "-subj",
                "/CN=InfraBadge Edge CASA",
            ]
        )
        checked_now = time.time()
        if abs(checked_now - now) > 30:
            raise ValueError("clock_changed_during_issuance")
        result = pki.validate(
            cert, None, config["ca_file"], config["sans"], checked_now, minimum=10 * pki.DAY
        )
        if result["not_after"] > after:
            raise ValueError("issuer_ca_expiry")
        return cert.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        os.umask(0o077)
        if (
            os.getuid() != 0
            or pki.command(
                [
                    "/usr/bin/timedatectl",
                    "show",
                    "--property=NTPSynchronized",
                    "--value",
                ]
            ).strip()
            != b"yes"
        ):
            raise ValueError("signer_identity_clock")
        raw = sys.stdin.buffer.read(16385)
        sys.stdout.buffer.write(sign(lifecycle.load(args.config), raw, time.time()))
        return 0
    except Exception:
        print("signer_rejected", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
