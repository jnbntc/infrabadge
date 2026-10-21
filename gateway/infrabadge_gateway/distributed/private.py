"""Private local inputs. Never log their contents or follow a final symlink."""

import json
import os
import stat
from pathlib import Path

from ..app import bounded_json


def private_bytes(path, maximum=131072):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("private regular file required")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError("private input too large")
        return raw
    finally:
        os.close(fd)


def read_json(path):
    return bounded_json(private_bytes(path))


def private_parent(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("symlink not allowed")
    info = path.parent.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("private owned directory required")
    return path


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
