#!/usr/bin/env python3
"""Check inert native artifacts in temporary paths; never installs or contacts a host."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "deploy/m32/native"


def lock_entries(path):
    entries = {}
    for block in re.split(r"\n\s*\n", path.read_text()):
        match = re.search(r"^([\w.-]+)==([^\s\\]+)", block, re.M)
        if match:
            key = match[1].lower().replace("_", "-")
            if key in entries:
                raise ValueError("duplicate lock entry")
            hashes = set(re.findall(r"--hash=sha256:([a-f0-9]{64})", block))
            if not hashes:
                raise ValueError("hashed version required")
            entries[key] = (match[2], hashes)
    return entries


def check(verify_systemd=False):
    runtime = lock_entries(NATIVE / "requirements-runtime.lock")
    full = lock_entries(ROOT / "gateway/requirements.lock")
    if len(runtime) != 17 or any(full.get(k) != v for k, v in runtime.items()):
        raise ValueError("runtime must be the approved hashed subset")
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        release = folder / "release"
        (release / "venv/bin").mkdir(parents=True)
        (release / "venv/bin/python").symlink_to(sys.executable)
        replacements = {
            "@RELEASE_DIR@": str(release),
            "@ADAPTER_PATH@": str(NATIVE / "core_sockets.py"),
            "@CORE_USER@": "65534",
            "@CORE_GROUP@": "65534",
            "@COLLECTOR_USER@": "65533",
            "@COLLECTOR_GROUP@": "65533",
            "@COLLECTOR_UNIT@": "infrabadge-m32-collector",
            "@COLLECTOR_STATE_DIR@": str(folder / "state"),
            "@COLLECTOR_CONFIG_DIR@": str(folder / "config"),
            "@COLLECTOR_CREDENTIAL@": str(folder / "credential-not-created"),
            "@INTERVAL_SECONDS@": "60",
            # Documentation-only TEST-NET address, never bound or contacted.
            "@TAILNET_IPV4@": "192.0.2.1",
        }
        rendered = []
        for template in sorted(NATIVE.glob("*.in")):
            text = template.read_text()
            for key, value in replacements.items():
                text = text.replace(key, value)
            if re.search(r"@[A-Z_]+@", text):
                raise ValueError("unresolved template field")
            if "collector.service" in template.name:
                assert "ExecStartPre=/usr/bin/install -m 0600 %d/collector-token" in text
                assert "RuntimeDirectoryMode=0700" in text and "RuntimeDirectoryPreserve=no" in text
                assert "-I -B" in text and "LoadCredential=collector-token:" in text
            if "collector.timer" in template.name:
                assert "Persistent=false" in text and "WakeSystem=false" in text
                assert "OnUnitInactiveSec=60s" in text
            if "core.socket" in template.name:
                assert text.count("ListenStream=") == 2 and "Accept=no" in text
                assert "FreeBind=yes" in text and "0.0.0.0" not in text
            if "core.service" in template.name:
                assert "Sockets=infrabadge-m32-core.socket" in text
                assert "--listener 127.0.0.1 --listener 192.0.2.1" in text
                assert "ProtectSystem=strict" in text and "LimitAS=512M" in text
            path = folder / template.name.removesuffix(".in")
            path.write_text(text)
            rendered.append(path)
        assert len(rendered) == 4
        if verify_systemd:
            subprocess.run(
                ["systemd-analyze", "verify", "--man=no", *map(str, rendered)],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
    return dict(
        status="PASS",
        runtime_packages=17,
        templates=4,
        systemd_syntax_verified=verify_systemd,
        installed=False,
        hosts_contacted=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-systemd", action="store_true")
    print(json.dumps(check(parser.parse_args().verify_systemd)))
