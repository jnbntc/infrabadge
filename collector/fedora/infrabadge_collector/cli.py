"""Fedora host oneshot. Errors are allowlisted codes, never source contents."""

import argparse
import contextlib
import errno
import fcntl
import json
import os
import sys
import time
from pathlib import Path

from .acquire import acquire
from .runtime import load_baseline, load_config, require_host, save_baseline
from .transport import submit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Read host metrics locally; no token, network or persistent state",
    )
    args = parser.parse_args()
    os.umask(0o077)
    try:
        require_host()
        if args.sample:
            _, baseline = acquire("workstation", "/var/home", "HOME")
            time.sleep(1)
            metrics, _ = acquire("workstation", "/var/home", "HOME", baseline)
            print(json.dumps(metrics, allow_nan=False, separators=(",", ":")))
            return 0
        if not args.config or not args.token_file:
            parser.error("--config and --token-file are required unless --sample")
        config = load_config(args.config)
        state = Path(config["state_file"])
        # Own state directory only. Never mkdir arbitrary host mount/config paths.
        if not state.parent.is_dir() or state.parent.stat().st_mode & 0o077:
            raise ValueError("private_state_directory_required")
        with contextlib.ExitStack() as stack:
            locked = False
            try:
                fd = os.open(str(state) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                lock = stack.enter_context(os.fdopen(fd, "w"))
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as error:
                if error.errno not in (errno.ENOSPC, errno.EDQUOT, errno.EROFS):
                    raise
                state_warning()
            # If a full/read-only state filesystem prevents locking, publish
            # available metrics with CPU warmup, never an unsafe shared delta.
            previous = load_baseline(state) if locked else None
            metrics, baseline = acquire(
                config["node_id"],
                config["mount_path"],
                config["mount_id"],
                previous,
                max_gap=config["interval_seconds"] * 3,
            )
            if baseline and locked:
                try:
                    save_baseline(state, baseline)
                except OSError:
                    state_warning()  # A cache write must not suppress a disk-full alarm.
            submit(config, args.token_file, metrics)
        print(
            json.dumps(
                {"component": "collector", "event": "submitted", "node_id": config["node_id"]}
            )
        )
        return 0
    except Exception:
        # No exception repr/traceback: filesystem, URL, credentials and payload stay private.
        print(
            json.dumps(
                {
                    "component": "collector",
                    "event": "failed",
                    "error_code": "collection_or_submission_failed",
                }
            ),
            file=sys.stderr,
        )
        return 1


def state_warning():
    print(
        json.dumps(
            {"component": "collector", "event": "warning", "error_code": "cpu_state_unavailable"}
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
