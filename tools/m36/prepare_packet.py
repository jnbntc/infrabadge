"""Prepare a private IBPROV36 packet offline. Never opens serial or changes NVS."""

import argparse
import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def private_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 11000
        ):
            raise ValueError("private file required")
        return os.read(fd, 11001)
    finally:
        os.close(fd)


def prepare(source, output, validator):
    data = private_read(source)

    # Reject duplicates before compacting; the C parser remains authoritative.
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate field")
            out[key] = value
        return out

    data = json.dumps(
        json.loads(data, object_pairs_hook=pairs),
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    checked = subprocess.run([str(validator), "--validate"], input=data, capture_output=True)
    if checked.returncode or checked.stdout or checked.stderr:
        raise ValueError("invalid configuration")
    parent = output.parent
    if (
        parent.is_symlink()
        or stat.S_IMODE(parent.stat().st_mode) != 0o700
        or parent.stat().st_uid != os.getuid()
    ):
        raise ValueError("private directory required")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(b"IBPROV36 " + data + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validator", type=Path, default=ROOT / "results/m36-native/policy")
    args = parser.parse_args()
    try:
        prepare(args.config, args.output, args.validator)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        parser.exit(1, "Preparación detenida; no se abrió USB ni se escribió la placa.\n")
    print(
        "Paquete privado preparado sin acceso a USB. Requiere autorización de provisión y UTC fresco antes de usarlo."
    )


if __name__ == "__main__":
    main()
