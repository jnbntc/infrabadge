"""Bounded OpenSSL operations; no CA key is loaded by the monitor or renewer."""

import hashlib
import ipaddress
import os
import re
import ssl
import stat
import subprocess
from pathlib import Path

DAY = 86400


def command(args, *, data=None, timeout=5):
    # No shell, environment-controlled OpenSSL configuration, or unbounded output on disk.
    result = subprocess.run(
        args,
        input=data,
        capture_output=True,
        check=True,
        timeout=timeout,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "OPENSSL_CONF": "/dev/null"},
    )
    if len(result.stdout) > 65536:
        raise ValueError("command_output_limit")
    return result.stdout


def private(path, owner, maximum=65536, *, read=True):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("private_path")
    for parent in path.parents:
        info = parent.stat()
        if info.st_uid not in (0, owner) or (
            info.st_mode & 0o022 and not (info.st_uid == 0 and info.st_mode & stat.S_ISVTX)
        ):
            raise ValueError("unsafe_parent")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_mode & 0o077:
            raise ValueError("private_owner_mode")
        if not read:
            return None
        raw = os.read(fd, maximum + 1)
        if len(raw) > maximum:
            raise ValueError("private_size")
        return raw
    finally:
        os.close(fd)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dates(path):
    raw = command(["/usr/bin/openssl", "x509", "-in", str(path), "-noout", "-dates"])
    fields = dict(line.split("=", 1) for line in raw.decode("ascii").splitlines())
    return tuple(ssl.cert_time_to_seconds(fields[k]) for k in ("notBefore", "notAfter"))


def san_names(names):
    if type(names) is not list or not 1 <= len(names) <= 8 or len(set(names)) != len(names):
        raise ValueError("san_list")
    result = []
    for name in names:
        if type(name) is not str:
            raise ValueError("san_type")
        try:
            result.append("IP:" + str(ipaddress.ip_address(name)))
        except ValueError:
            if len(name) > 253 or not all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in name.split(".")
            ):
                raise ValueError("san_dns") from None
            result.append("DNS:" + name)
    return result


def certificate_sans(path):
    lines = (
        command(
            [
                "/usr/bin/openssl",
                "x509",
                "-in",
                str(path),
                "-noout",
                "-ext",
                "subjectAltName",
            ]
        )
        .decode("ascii")
        .splitlines()
    )
    if not lines or "Subject Alternative Name" not in lines[0]:
        raise ValueError("missing_san")
    return sorted("".join(lines[1:]).strip().replace("IP Address:", "IP:").split(", "))


def validate(cert, key, ca, names, now, *, minimum=0):
    """Exact approved SAN set, server purpose, CA chain/dates, matching private key."""
    before, after = dates(cert)
    ca_before, ca_after = dates(ca)
    if not ca_before <= now < ca_after or not before <= now < after:
        raise ValueError("certificate_dates")
    if after - now < minimum or after > ca_after:
        raise ValueError("insufficient_validity")
    if certificate_sans(cert) != sorted(san_names(names)):
        raise ValueError("san_drift")
    command(
        [
            "/usr/bin/openssl",
            "verify",
            "-x509_strict",
            "-purpose",
            "sslserver",
            "-attime",
            str(int(now)),
            "-CAfile",
            str(ca),
            str(cert),
        ]
    )
    constraints = command(
        [
            "/usr/bin/openssl",
            "x509",
            "-in",
            str(cert),
            "-noout",
            "-ext",
            "basicConstraints,extendedKeyUsage",
        ]
    ).decode("ascii")
    if "CA:FALSE" not in constraints or "TLS Web Server Authentication" not in constraints:
        raise ValueError("leaf_constraints")
    if key is not None:
        pub = command(["/usr/bin/openssl", "x509", "-in", str(cert), "-noout", "-pubkey"])
        pair = command(["/usr/bin/openssl", "pkey", "-in", str(key), "-pubout"])
        if pub != pair:
            raise ValueError("key_mismatch")
    return {"not_before": before, "not_after": after, "remaining": after - now}


def csr(directory, names):
    key, request = directory / "server.key", directory / "request.pem"
    command(
        [
            "/usr/bin/openssl",
            "req",
            "-new",
            "-newkey",
            "ec",
            "-pkeyopt",
            "ec_paramgen_curve:P-256",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(request),
            "-subj",
            "/CN=InfraBadge Edge CASA",
            "-addext",
            "subjectAltName=" + ",".join(san_names(names)),
        ]
    )
    key.chmod(0o600)
    request.chmod(0o600)
    return key, request
