"""Single-process SQLite repository; durable replay floor and bounded history."""

import contextlib
import fcntl
import os
import sqlite3
import threading
import time

from .private import private_parent

SCHEMA_VERSION = 2
MIGRATIONS = {
    1: (
        "CREATE TABLE sites(id TEXT PRIMARY KEY, definition TEXT NOT NULL)",
        "CREATE TABLE nodes(id TEXT PRIMARY KEY, site_id TEXT NOT NULL REFERENCES sites(id), definition TEXT NOT NULL)",
    ),
    2: (
        "CREATE TABLE latest(node TEXT PRIMARY KEY REFERENCES nodes(id), collected INTEGER NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL, evaluation TEXT NOT NULL, session TEXT NOT NULL, received INTEGER NOT NULL)",
        "CREATE TABLE history(node TEXT NOT NULL REFERENCES nodes(id), collected INTEGER NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(node,collected))",
        "CREATE TABLE snapshots(device TEXT PRIMARY KEY, revision INTEGER NOT NULL, fingerprint TEXT NOT NULL, body TEXT NOT NULL, session TEXT NOT NULL)",
        "CREATE TABLE metadata(key TEXT PRIMARY KEY, value INTEGER NOT NULL)",
        "INSERT INTO metadata VALUES('clock_floor',0)",
    ),
}


class Unavailable(Exception):
    pass


class ClockUntrusted(Unavailable):
    pass


class Store:
    def __init__(self, path, *, migrate=False):
        self.path = private_parent(path)
        self.lock = threading.RLock()
        self.db = None
        self.owner = None
        new = not self.path.exists()
        if not new and self.path.stat().st_size > 128 * 1024 * 1024:
            raise ValueError("database bound exceeded")
        try:
            if self.path.exists() and (
                not self.path.is_file()
                or self.path.stat().st_uid != os.getuid()
                or self.path.stat().st_mode & 0o077
            ):
                raise ValueError("private database required")
            fd = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            self.owner = os.fdopen(fd, "w")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if new:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            self.db = sqlite3.connect(
                self.path, timeout=1, check_same_thread=False, isolation_level=None
            )
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA trusted_schema=OFF")
            self.db.execute("PRAGMA busy_timeout=1000")
            self.db.execute("PRAGMA max_page_count=32768")  # 128 MiB with required4096B pages.
            if self.db.execute("PRAGMA page_size").fetchone()[0] != 4096:
                raise ValueError("unsupported page size")
            if self.db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("database integrity")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION or (not new and version < SCHEMA_VERSION and not migrate):
                raise ValueError("explicit migration or supported schema required")
            if (
                version == 0
                and self.db.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()[0]
            ):
                raise ValueError("unrecognized database")
            # DELETE/FULL deliberately avoids a WAL dependency and network-FS assumptions.
            if self.db.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise ValueError("DELETE journal required")
            self.db.execute("PRAGMA synchronous=FULL")
            for target in range(version + 1, SCHEMA_VERSION + 1):
                with self.transaction() as db:
                    for sql in MIGRATIONS[target]:
                        db.execute(sql)
                    db.execute(f"PRAGMA user_version={target}")
        except Exception:
            self.close()
            raise

    @contextlib.contextmanager
    def transaction(self):
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                yield self.db
                self.db.execute("COMMIT")
            except sqlite3.Error as error:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise Unavailable("storage unavailable") from error
            except BaseException:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                raise

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        if self.owner is not None:
            self.owner.close()
            self.owner = None

    def backup(self, destination):
        destination = private_parent(destination)
        if destination.exists() or destination.is_symlink():
            raise ValueError("new backup required")
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            with self.lock, sqlite3.connect(destination) as output:
                self.db.backup(output, pages=64, progress=backup_deadline())
                if output.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise Unavailable("backup integrity")
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination


def restore(source, destination):
    """Offline validated copy into NEW destination. Never replaces current DB."""
    source = private_parent(source)
    if source.stat().st_mode & 0o077 or source.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("private backup required")
    destination = private_parent(destination)
    if destination.exists():
        raise ValueError("new destination required")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as db:
            db.execute("PRAGMA trusted_schema=OFF")
            if (
                db.execute("PRAGMA integrity_check").fetchone() != ("ok",)
                or db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION
            ):
                raise Unavailable("backup integrity/schema")
            with sqlite3.connect(destination) as output:
                db.backup(output, pages=64, progress=backup_deadline())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def backup_deadline():
    end = time.monotonic() + 10

    def check(status, remaining, total):
        if time.monotonic() > end:
            raise Unavailable("backup deadline")

    return check


def backup_file(source, destination):
    # SQLite backup API coordinates with the running writer; no process lease.
    return restore(source, destination)
