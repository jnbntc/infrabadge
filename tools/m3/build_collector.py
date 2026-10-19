#!/usr/bin/env python3
"""Reproducible stdlib-only zipapp; no pip or toolchain installation."""

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = {
        "__main__.py": b"from infrabadge_collector.cli import main\nraise SystemExit(main())\n"
    }
    for path in sorted((ROOT / "collector/fedora/infrabadge_collector").glob("*.py")):
        entries["infrabadge_collector/" + path.name] = path.read_bytes()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "  " + output.name + "\n")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "results/m3-package/infrabadge-collector.pyz"
    )
    args = parser.parse_args()
    print("Collector ZIP SHA-256: " + build(args.output))


if __name__ == "__main__":
    main()
