#!/usr/bin/env python3
"""Prepare user files only after --install. Never starts/enables any unit."""

import argparse
import os
import shutil
import sys
from pathlib import Path

from build_collector import ROOT, build


def install(home):
    share = home / ".local/share/infrabadge-collector"
    units = home / ".config/systemd/user"
    config = home / ".config/infrabadge"
    state = home / ".local/state/infrabadge-collector"
    targets = [
        share / "infrabadge-collector.pyz",
        share / "infrabadge-collector.pyz.sha256",
        units / "infrabadge-collector.service",
        units / "infrabadge-collector.timer",
    ]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise ValueError("existing_installation_preserved")
    # Private directories must already be private if present: no changing an
    # existing directory's permissions or following a redirected installation.
    for directory in (share, config, state):
        if directory.is_symlink() or (directory.exists() and directory.stat().st_mode & 0o077):
            raise ValueError("existing_directory_not_private")
    for directory in (share, config, state):
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    units.mkdir(parents=True, exist_ok=True)
    build(share / "infrabadge-collector.pyz")
    for name in ("infrabadge-collector.service", "infrabadge-collector.timer"):
        shutil.copyfile(ROOT / "deploy/m3" / name, units / name)
    example = config / "collector.example.json"
    if not example.exists():
        shutil.copyfile(ROOT / "deploy/m3/collector.example.json", example)
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run as the normal user, without sudo")
    if not args.install:
        print(
            "Preview: installs ZIP and two user units; creates private config/state folders. No services started. Use --install explicitly."
        )
        return 0
    os.umask(0o077)
    try:
        install(Path.home())
    except (OSError, ValueError):
        print(
            "Installation stopped; existing files preserved. Review local paths privately.",
            file=sys.stderr,
        )
        return 1
    print(
        "Files prepared. Configure private CA/token/config, then explicitly enable the timer as documented."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
