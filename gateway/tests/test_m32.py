"""Synthetic multisite fixtures only: no inventory, network or host services."""

import concurrent.futures
import copy
import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.config import CoreConfig
from infrabadge_gateway.distributed.core import Core, Rejected, aggregate
from infrabadge_gateway.distributed.store import (
    MIGRATIONS,
    ClockUntrusted,
    Store,
    Unavailable,
    restore,
)
from infrabadge_gateway.models import Snapshot
from m32_fixtures import NOW, TOKENS, configuration, headers, sample


@pytest.fixture
def engine(tmp_path):
    tmp_path.chmod(0o700)
    store = Store(tmp_path / "core.db")
    core = Core(configuration(), store)
    try:
        yield core
    finally:
        store.close()


def test_ingress_exact_m3_ack_and_m2_conditional_contract(engine):
    now = [NOW]
    with TestClient(
        create_app(engine, clock=lambda: now[0], budget_clock=lambda: now[0])
    ) as client:
        reply = client.post(
            "/api/v1/collectors/a/metrics",
            json=sample().model_dump(),
            headers=headers("collector-a"),
        )
        assert reply.status_code == 202 and reply.json() == {"accepted": True}
        first = client.get(
            "/api/v1/devices/display-a/status", headers=headers("d-device", "e-edge")
        )
        assert first.status_code == 200
        parsed = Snapshot.model_validate(first.json())
        assert parsed.status == "HEALTHY" and not parsed.simulated and parsed.counts.healthy == 1
        cached = client.get(
            "/api/v1/devices/display-a/status",
            headers=headers("d-device", "e-edge", **{"If-None-Match": first.headers["etag"]}),
        )
        assert cached.status_code == 304 and cached.content == b""
        now[0] += 180
        stale = client.get(
            "/api/v1/devices/display-a/status",
            headers=headers("d-device", "e-edge", **{"If-None-Match": first.headers["etag"]}),
        )
        assert stale.status_code == 200 and stale.json()["status"] == "UNKNOWN"
        assert "DATOS HISTORICOS" in stale.text


@pytest.mark.parametrize(
    "key,edge,device,expected",
    [
        ("collector-a", "e-edge", "display-a", 401),
        ("d-device", None, "display-a", 401),
        ("d-device", "g-edge", "display-a", 403),
        ("f-device", "e-edge", "display-a", 401),
        ("r-reader", "e-edge", "display-a", 401),
    ],
)
def test_roles_and_edge_scope_are_independent(engine, key, edge, device, expected):
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        assert (
            client.get(
                "/api/v1/devices/" + device + "/status", headers=headers(key, edge)
            ).status_code
            == expected
        )


def test_inventory_site_isolation_and_disabled_nodes(engine):
    engine.ingest("a", sample(), NOW)
    engine.ingest("b", sample("b", cpu=99.0), NOW)
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        assert (
            client.get("/api/v1/sites/beta/nodes", headers=headers("r-reader")).status_code == 403
        )
        one = client.get("/api/v1/sites/alpha/nodes", headers=headers("r-reader"))
        assert one.status_code == 200 and len(one.json()["nodes"]) == 1
        assert one.json()["nodes"][0]["node_id"] == "a"
        assert (
            client.get("/api/v1/sites/alpha/nodes", headers=headers("collector-a")).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/collectors/b/metrics",
                json=sample("b").model_dump(),
                headers=headers("collector-a"),
            ).status_code
            == 401
        )


def test_duplicate_ack_does_not_refresh_latches_or_seen_and_replay_survives_restart(engine):
    s = sample(cpu=99.0)
    engine.ingest("a", s, NOW)
    engine.ingest("a", s, NOW + 20)
    v = engine.inventory("alpha", NOW + 20)["nodes"][0]
    assert v["status"] == "HEALTHY" and v["last_seen"] == NOW
    bad = s.model_copy(update={"uptime_seconds": 1010.0})
    with pytest.raises(Rejected) as e:
        engine.ingest("a", bad, NOW + 20)
    assert e.value.status == 409
    restarted = Core(configuration(), engine.store)
    restarted.ingest("a", s, NOW + 21)  # ACK loss: receipt accepted, never marked fresh.
    v = restarted.inventory("alpha", NOW + 21)["nodes"][0]
    assert v["freshness"] == "restored" and v["metrics"] is None
    with pytest.raises(Rejected):
        restarted.ingest("a", sample(at=NOW - 30), NOW + 21)
    restarted.ingest("a", sample(at=NOW + 60), NOW + 60)
    assert restarted.inventory("alpha", NOW + 60)["status"] == "HEALTHY"


def test_node_stale_offline_recovery_and_mobile_suspension(engine):
    engine.ingest("b", sample("b"), NOW)
    assert engine.inventory("beta", NOW + 180)["status"] == "UNKNOWN"
    assert engine.inventory("beta", NOW + 600)["status"] == "OFFLINE"
    # Long gap starts a new CPU confirmation window; no catch-up backlog.
    engine.ingest("b", sample("b", NOW + 1200, cpu=99.0), NOW + 1200)
    assert engine.inventory("beta", NOW + 1200)["status"] == "HEALTHY"


def test_cpu_window_critical_recovery_and_transactional_history(engine):
    for offset in (0, 60, 120):
        engine.ingest("a", sample(at=NOW + offset, cpu=99.0), NOW + offset)
    assert engine.inventory("alpha", NOW + 120)["status"] == "CRITICAL"
    engine.ingest("a", sample(at=NOW + 180, cpu=20.0), NOW + 180)
    assert engine.inventory("alpha", NOW + 180)["status"] == "CRITICAL"
    engine.ingest("a", sample(at=NOW + 240, cpu=20.0), NOW + 240)
    assert engine.inventory("alpha", NOW + 240)["status"] == "HEALTHY"
    assert engine.store.db.execute("SELECT count(*) FROM history").fetchone()[0] == 5


@pytest.mark.parametrize(
    "states,result",
    [
        ([], "UNKNOWN"),
        (["HEALTHY"], "HEALTHY"),
        (["OFFLINE"], "OFFLINE"),
        (["OFFLINE", "UNKNOWN"], "UNKNOWN"),
        (["OFFLINE", "HEALTHY"], "UNKNOWN"),
        (["UNKNOWN", "WARNING"], "WARNING"),
        (["CRITICAL", "OFFLINE"], "CRITICAL"),
    ],
)
def test_aggregation_precedence(states, result):
    assert aggregate(states) == result


def test_multisite_aggregate_preserves_scope_and_earliest_expiry(engine):
    cfg = configuration()
    cfg.devices["display-a"].site_ids = ["alpha", "beta"]
    core = Core(cfg, engine.store)
    core.ingest("a", sample(), NOW)
    core.ingest("b", sample("b", available=3), NOW)
    snap = Snapshot.model_validate_json(core.snapshot("display-a", NOW))
    assert snap.status == "CRITICAL" and snap.counts.critical == 1 and snap.counts.healthy == 1
    assert snap.expires_at <= NOW + 180
    body = core.snapshot("display-b", NOW)
    assert "NODE_A" not in body.decode()


def test_empty_disabled_inventory_is_explicit_control_not_invented_node(engine):
    cfg = configuration()
    cfg.nodes["a"].enabled = False
    core = Core(cfg, engine.store)
    with pytest.raises(Rejected):
        core.ingest("a", sample(), NOW)
    snap = Snapshot.model_validate_json(core.snapshot("display-a", NOW))
    assert snap.status == "UNKNOWN" and "SIN NODOS" in snap.alerts[0].title
    assert core.inventory("alpha", NOW)["nodes"][0]["freshness"] == "disabled"


def test_concurrent_collectors_and_duplicate_delivery(engine):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: engine.ingest(n, sample(n), NOW), ["a", "b"] * 4))
    assert engine.store.db.execute("SELECT count(*) FROM latest").fetchone() == (2,)
    assert engine.store.db.execute("SELECT count(*) FROM history").fetchone() == (2,)


@pytest.mark.parametrize(
    "change,status",
    [
        ({"schema_version": 99}, 422),
        ({"collected_at": NOW + 1}, 422),
        ({"collected_at": NOW - 180}, 422),
        ({"node_id": "b"}, 422),
        ({"extra": "private"}, 422),
    ],
)
def test_invalid_samples_never_advance_state(engine, change, status):
    value = sample().model_dump() | change
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        r = client.post("/api/v1/collectors/a/metrics", json=value, headers=headers("collector-a"))
        assert r.status_code == status and "private" not in r.text
    assert engine.store.db.execute("SELECT count(*) FROM latest").fetchone() == (0,)


def test_bounded_body_duplicate_json_auth_headers_and_rate(engine):
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        assert (
            client.post(
                "/api/v1/collectors/a/metrics",
                content="x" * 8193,
                headers=headers("collector-a", **{"Content-Type": "application/json"}),
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/v1/collectors/a/metrics",
                content='{"schema_version":1,"schema_version":1}',
                headers=headers("collector-a", **{"Content-Type": "application/json"}),
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/collectors/a/metrics",
                json=sample().model_dump(),
                headers=headers("collector-a"),
            ).status_code
            == 429
        )
        assert (
            client.get(
                "/api/v1/sites/alpha/nodes",
                headers=[("Authorization", "Bearer " + TOKENS["r-reader"])] * 2,
            ).status_code
            == 401
        )


def test_retention_watermark_clock_rollback_and_no_tokens_in_database(tmp_path):
    tmp_path.chmod(0o700)
    store = Store(tmp_path / "bounded.db")
    cfg = configuration(history_per_node=2, history_seconds=120)
    core = Core(cfg, store)
    for offset in (0, 60, 120, 180):
        core.ingest("a", sample(at=NOW + offset), NOW + offset)
    assert store.db.execute("SELECT count(*) FROM history").fetchone() == (2,)
    with pytest.raises(ClockUntrusted):
        core.snapshot("display-a", NOW)
    with pytest.raises(Rejected):
        core.ingest("a", sample(), NOW + 181)
    store.close()
    raw = (tmp_path / "bounded.db").read_bytes()
    assert not any(v.encode() in raw for v in TOKENS.values())
    assert not any(hashlib.sha256(v.encode()).hexdigest().encode() in raw for v in TOKENS.values())


def test_restart_backup_restore_historical_only_and_revision_persists(engine, tmp_path):
    engine.ingest("a", sample(), NOW)
    before = Snapshot.model_validate_json(engine.snapshot("display-a", NOW))
    backup = engine.store.backup(tmp_path / "backup.db")
    restored = restore(backup, tmp_path / "restore.db")
    store = Store(restored)
    try:
        core = Core(configuration(), store)
        view = core.inventory("alpha", NOW + 1)["nodes"][0]
        assert (
            view["metrics"] is None
            and view["freshness"] == "restored"
            and view["historical_metrics"]
        )
        after = Snapshot.model_validate_json(core.snapshot("display-a", NOW + 1))
        assert after.revision > before.revision and after.status == "UNKNOWN"
        assert not after.simulated
    finally:
        store.close()
    with pytest.raises(ValueError):
        restore(backup, restored)


def test_migrations_future_version_corruption_symlink_and_single_writer(tmp_path):
    tmp_path.chmod(0o700)
    path = tmp_path / "v1.db"
    with sqlite3.connect(path) as db:
        for sql in MIGRATIONS[1]:
            db.execute(sql)
        db.execute("PRAGMA user_version=1")
    path.chmod(0o600)
    with pytest.raises(ValueError):
        Store(path)
    store = Store(path, migrate=True)
    assert store.db.execute("PRAGMA user_version").fetchone() == (2,)
    with pytest.raises((OSError, ValueError)):
        Store(path)
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=99")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        Store(path, migrate=True)
    assert path.read_bytes() == original
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"not sqlite PRIVATE DATA")
    broken.chmod(0o600)
    with pytest.raises(sqlite3.DatabaseError):
        Store(broken)
    assert broken.read_bytes() == b"not sqlite PRIVATE DATA"
    with pytest.raises(Exception):
        restore(broken, tmp_path / "rejected.db")
    assert not (tmp_path / "rejected.db").exists()
    link = tmp_path / "link.db"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        Store(link)


def test_sqlite_error_rolls_back_and_cannot_ack_failed_sample(engine):
    engine.store.db.execute(
        'CREATE TRIGGER fail_history BEFORE INSERT ON history BEGIN SELECT RAISE(ABORT,"private failure"); END'
    )
    with pytest.raises(Unavailable):
        engine.ingest("a", sample(), NOW)
    assert engine.store.db.execute("SELECT count(*) FROM latest").fetchone() == (0,)
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        r = client.post(
            "/api/v1/collectors/a/metrics",
            json=sample().model_dump(),
            headers=headers("collector-a"),
        )
        assert r.status_code == 503 and "private failure" not in r.text


def test_corrupt_health_data_is_unavailable_not_healthy(engine):
    engine.ingest("a", sample(), NOW)
    engine.store.db.execute(
        "UPDATE latest SET evaluation=?", (json.dumps({"status": "INVENTED", "latches": []}),)
    )
    with TestClient(create_app(engine, clock=lambda: NOW)) as client:
        r = client.get("/api/v1/devices/display-a/status", headers=headers("d-device", "e-edge"))
        assert r.status_code == 503


def test_inventory_validates_unknown_sites_scopes_and_credentials():
    raw = configuration().model_dump()
    bad = copy.deepcopy(raw)
    bad["nodes"]["a"]["site_id"] = "missing"
    with pytest.raises(ValueError):
        CoreConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["devices"]["display-a"]["token_sha256"] = bad["collectors"]["a"]["token_sha256"]
    with pytest.raises(ValueError):
        CoreConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["edges"]["edge-a"]["device_ids"] = ["missing"]
    with pytest.raises(ValueError):
        CoreConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["devices"]["display-a"]["site_ids"] = ["alpha", "alpha"]
    with pytest.raises(ValueError):
        CoreConfig.model_validate(bad)


def test_node_reassignment_cannot_leak_history_to_another_site(engine):
    engine.ingest("a", sample(), NOW)
    changed = configuration()
    changed.nodes["a"].site_id = "beta"
    with pytest.raises(ValueError):
        Core(changed, engine.store)
    assert engine.inventory("alpha", NOW)["nodes"][0]["site_id"] == "alpha"


def test_backup_api_works_with_running_writer_and_retention_is_consistent(engine, tmp_path):
    from infrabadge_gateway.distributed.store import backup_file

    engine.ingest("a", sample(), NOW)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(
            lambda: [
                engine.ingest("a", sample(at=NOW + offset), NOW + offset)
                for offset in (60, 120, 180)
            ]
        )
        destination = backup_file(engine.store.path, tmp_path / "online.db")
        task.result()
    with sqlite3.connect(destination) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("SELECT count(*) FROM latest").fetchone() == (1,)
        assert (
            db.execute("SELECT max(collected) FROM history").fetchone()[0]
            == db.execute("SELECT collected FROM latest").fetchone()[0]
        )


def test_snapshot_never_outlives_earliest_fresh_sample(engine):
    engine.ingest("a", sample(), NOW)
    body = Snapshot.model_validate_json(engine.snapshot("display-a", NOW + 170))
    assert body.expires_at == NOW + 180
    after = Snapshot.model_validate_json(engine.snapshot("display-a", NOW + 180))
    assert after.status == "UNKNOWN" and after.revision > body.revision


def test_check_command_never_creates_an_absent_database(tmp_path, monkeypatch, capsys):
    from infrabadge_gateway.distributed import cli

    path = tmp_path / "absent.db"
    monkeypatch.setattr("sys.argv", ["distributed", "check", "--database", str(path)])
    monkeypatch.setattr(cli.os, "geteuid", lambda: 1000)
    assert cli.main() == 1
    assert not path.exists() and not path.with_suffix(".db.lock").exists()
    assert json.loads(capsys.readouterr().out)["event"] == "unavailable"
