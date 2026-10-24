"""Render inert units to a new private directory. Never copies credentials or installs."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def render(release):
    if not re.fullmatch(r"/opt/infrabadge-tls/releases/[a-f0-9]{40}", str(release)):
        raise ValueError("pinned_release_path")
    return {
        p.name.removesuffix(".in"): p.read_text().replace("@RELEASE@", str(release))
        for p in sorted((ROOT / "deploy/tls_lifecycle").glob("*.in"))
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.getuid() == 0:
        parser.error("prepare_as_unprivileged_user")
    output = args.output.absolute()
    if (
        output.exists()
        or output.is_relative_to(ROOT)
        or any(p.is_symlink() for p in output.parents)
    ):
        parser.error("new_private_directory_outside_repository_required")
    files = render(args.release)
    os.umask(0o077)
    output.mkdir(mode=0o700)
    for name, text in files.items():
        with (output / name).open("x") as stream:
            stream.write(text)
    manifest = {
        "schema_version": 1,
        "installed": False,
        "release": str(args.release),
        "files": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
    }
    with (output / "manifest.json").open("x") as stream:
        json.dump(manifest, stream, sort_keys=True)
    print(json.dumps({"installed": False, "unit_files": len(files)}))


if __name__ == "__main__":
    main()
