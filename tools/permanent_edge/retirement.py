"""Full retirement of exactly recorded CASA files. Preserves private evidence/PKI.

Called only after the independent watchdog stopped the listener and restored
the firewall, or after an operator stopped the permanent firewall service.
No arbitrary cleanup paths, Core control or database writes.
"""

import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import permanent


def roots(sha):
    if type(sha) is not str or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("retirement_release")
    return {
        Path("/etc/infrabadge-edge-home"),
        Path("/etc/infrabadge-edge-home-admin"),
        Path("/run/infrabadge-edge-home"),
        Path("/run/infrabadge-edge-home-admin"),
        Path("/opt/infrabadge-edges/releases") / sha,
        Path("/etc/systemd/system/infrabadge-edge-home.service.d"),
        Path("/var/lib/systemd/timers/stamp-infrabadge-edge-home-tls-check.timer"),
        *(Path("/etc/systemd/system") / name for name in permanent.UNIT_PATHS if "/" not in name),
        *(
            Path("/etc/systemd/system") / (permanent.STEM + suffix)
            for suffix in ("-rollback.service", "-rollback.timer")
        ),
        *(
            Path("/etc/systemd/system") / directory / name
            for directory, name in (
                ("multi-user.target.wants", permanent.STEM + ".service"),
                ("timers.target.wants", permanent.STEM + "-probe.timer"),
                ("timers.target.wants", permanent.STEM + "-tls-check.timer"),
            )
        ),
    }


def inventory(path):
    """Hash link text without following it (venv symlinks are expected)."""
    result = {}
    pending = [path]
    while pending:
        entry = pending.pop()
        info = entry.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            kind, digest = "link", hashlib.sha256(os.readlink(entry).encode()).hexdigest()
        elif stat.S_ISDIR(info.st_mode):
            kind, digest = "directory", None
            pending.extend(sorted(entry.iterdir()))
        elif stat.S_ISREG(info.st_mode):
            kind, digest = "file", hashlib.sha256(entry.read_bytes()).hexdigest()
        else:
            raise ValueError("unexpected_owned_file_type")
        result[str(entry.relative_to(path))] = {
            "kind": kind,
            "sha256": digest,
            "uid": info.st_uid,
            "gid": info.st_gid,
            "mode": mode,
        }
    return result


def record(sha, uid, gid, absent_before, fsroot=Path("/")):
    if (
        absent_before is not True
        or type(uid) is not int
        or type(gid) is not int
        or min(uid, gid) <= 0
    ):
        raise ValueError("explicit_prior_absence_and_account_required")
    files = {}
    for root in sorted(roots(sha)):
        path = fsroot / root.relative_to("/")
        if path.exists() or path.is_symlink():
            files[str(root)] = inventory(path)
    if "/etc/infrabadge-edge-home" not in files:
        raise ValueError("owned_configuration_required")
    return {
        "schema_version": 1,
        "release_sha": sha,
        "uid": uid,
        "gid": gid,
        "absent_before": True,
        "files": files,
    }


def verify(value, fsroot=Path("/")):
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "release_sha", "uid", "gid", "absent_before", "files"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["absent_before"] is not True
    ):
        raise ValueError("retirement_schema")
    if any(type(value[k]) is not int or value[k] <= 0 for k in ("uid", "gid")):
        raise ValueError("retirement_account")
    allowed = roots(value["release_sha"])
    if (
        type(value["files"]) is not dict
        or not value["files"]
        or any(Path(p) not in allowed for p in value["files"])
    ):
        raise ValueError("retirement_scope")
    for root in allowed:
        path = fsroot / root.relative_to("/")
        if str(root) in value["files"]:
            if inventory(path) != value["files"][str(root)]:
                raise ValueError("retirement_file_drift")
        elif path.exists() or path.is_symlink():
            raise ValueError("unrecorded_edge_object")


def archive_files(value, archive, fsroot=Path("/")):
    """Verify first; retain a private copy before retiring tmpfs runtime entries."""
    verify(value, fsroot)
    if archive.exists() or archive.is_symlink() or any(p.is_symlink() for p in archive.parents):
        raise ValueError("fresh_private_archive_required")
    archive.mkdir(mode=0o700)
    moved = []
    try:
        for name in sorted(value["files"]):
            origin = fsroot / Path(name).relative_to("/")
            destination = archive / Path(name).relative_to("/")
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if origin.lstat().st_dev == archive.stat().st_dev:
                origin.rename(destination)
                moved.append((origin, destination, False))
            else:
                if name not in ("/run/infrabadge-edge-home", "/run/infrabadge-edge-home-admin"):
                    raise ValueError("unexpected_cross_filesystem_root")
                if any(item["kind"] == "link" for item in value["files"][name].values()):
                    raise ValueError("runtime_symlinks_not_allowed")
                shutil.copytree(origin, destination)

                def content(entries):
                    return {
                        k: {a: b for a, b in v.items() if a not in ("uid", "gid")}
                        for k, v in entries.items()
                    }

                if (
                    content(inventory(destination)) != content(value["files"][name])
                    or inventory(origin) != value["files"][name]
                ):
                    raise ValueError("runtime_archive_mismatch")
                moved.append((origin, destination, True))
                for relative, item in sorted(
                    value["files"][name].items(), key=lambda x: len(Path(x[0]).parts), reverse=True
                ):
                    path = origin / relative
                    if item["kind"] == "directory":
                        path.rmdir()
                    else:
                        path.unlink()
    except Exception:
        # Restore prior paths after a failed move/removal. Preserve the private archive.
        for origin, destination, copied in reversed(moved):
            if copied:
                shutil.copytree(destination, origin, dirs_exist_ok=True)
            else:
                destination.rename(origin)
        verify(value, fsroot)
        raise
    return {
        "event": "edge_retirement",
        "archived_roots": len(value["files"]),
        "credentials_deleted": False,
    }


def stopped_and_unowned_by_process(uid, run=subprocess.run, proc=Path("/proc")):
    listeners = run(
        ["/usr/bin/ss", "-H", "-lnt", "sport = :8443"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if listeners.stdout.strip():
        raise ValueError("listener_still_present")
    for entry in proc.iterdir():
        if entry.name.isdigit():
            try:
                # /proc/PID/status UIDs include real/effective/saved/fs identities.
                rows = (entry / "status").read_text().splitlines()
                uids = next(row for row in rows if row.startswith("Uid:")).split()[1:]
                if str(uid) in uids:
                    raise ValueError("edge_process_remains")
            except FileNotFoundError:
                continue
