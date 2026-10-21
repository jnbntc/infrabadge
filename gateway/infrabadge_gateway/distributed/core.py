"""Transactional multisite health using the validated M3 evaluator and M2 wire."""

import hashlib
import json
import secrets

from ..metrics import Evaluation, Latch, Metrics
from ..models import Alert, Counts, Snapshot
from .config import NodeView, SiteView
from .private import encode
from .store import ClockUntrusted


class Rejected(Exception):
    def __init__(self, status):
        self.status = status


def aggregate(states):
    if "CRITICAL" in states:
        return "CRITICAL"
    if "WARNING" in states:
        return "WARNING"
    if not states or any(s in ("UNKNOWN", "OFFLINE") for s in states):
        return "OFFLINE" if states and all(s == "OFFLINE" for s in states) else "UNKNOWN"
    return "HEALTHY"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def evaluation_state(evaluation):
    return encode(
        dict(
            status=evaluation.status,
            latches=[
                dict(name=k[0], severity=k[1], active=v.active, trip=v.trip, clear=v.clear)
                for k, v in sorted(evaluation.latches.items())
            ],
        )
    )


def restore_evaluation(row, session):
    evaluation = Evaluation()
    if row and row["session"] == session:
        evaluation.last = Metrics.model_validate_json(row["payload"])
        state = json.loads(row["evaluation"])
        if state["status"] not in ("UNKNOWN", "HEALTHY", "WARNING", "CRITICAL"):
            raise ValueError("stored health state")
        evaluation.status = state["status"]
        for item in state["latches"]:
            if (
                item["name"] not in ("cpu", "memory", "disk", "temperature")
                or item["severity"] not in ("warning", "critical")
                or type(item["active"]) is not bool
                or any(
                    type(item[k]) is not int or not 0 <= item[k] <= 30 for k in ("trip", "clear")
                )
            ):
                raise ValueError("stored health latch")
            latch = Latch()
            latch.active, latch.trip, latch.clear = item["active"], item["trip"], item["clear"]
            evaluation.latches[(item["name"], item["severity"])] = latch
    return evaluation


def latest(db, node):
    cursor = db.execute(
        "SELECT collected,digest,payload,evaluation,session,received FROM latest WHERE node=?",
        (node,),
    )
    row = cursor.fetchone()
    return dict(zip((d[0] for d in cursor.description), row)) if row else None


class Core:
    def __init__(self, config, store):
        self.config, self.store, self.session = config, store, secrets.token_hex(16)
        with store.transaction() as db:
            existing = {r[0] for r in db.execute("SELECT id FROM nodes")}
            if len(existing | set(config.nodes)) > 512:
                raise ValueError("retired inventory bound reached")
            for site, value in config.sites.items():
                db.execute(
                    "INSERT INTO sites VALUES(?,?) ON CONFLICT(id) DO UPDATE SET definition=excluded.definition",
                    (site, value.model_dump_json()),
                )
            for node, value in config.nodes.items():
                prior_site = db.execute("SELECT site_id FROM nodes WHERE id=?", (node,)).fetchone()
                if prior_site and prior_site[0] != value.site_id:
                    raise ValueError("explicit migration required to move node between sites")
                db.execute(
                    "INSERT INTO nodes VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET site_id=excluded.site_id,definition=excluded.definition",
                    (node, value.site_id, value.model_dump_json()),
                )

    def checked_clock(self, db, now):
        floor = db.execute("SELECT value FROM metadata WHERE key='clock_floor'").fetchone()[0]
        if type(now) is not int or not 1577836800 <= now <= 4102444800 or now < floor:
            raise ClockUntrusted("trusted UTC required")
        if now > floor:
            db.execute("UPDATE metadata SET value=? WHERE key='clock_floor'", (now,))

    def ingest(self, node_id, sample, now):
        node = self.config.nodes[node_id]
        policy = node.health_policy
        if not node.enabled or not self.config.sites[node.site_id].enabled:
            raise Rejected(403)
        if (
            sample.node_id != node_id
            or not 0 <= now - sample.collected_at < policy.sample_ttl_seconds
        ):
            raise Rejected(422)
        payload = encode(sample.model_dump())
        with self.store.transaction() as db:
            self.checked_clock(db, now)
            prior = latest(db, node_id)
            if prior and sample.collected_at <= prior["collected"]:
                if sample.collected_at == prior["collected"] and digest(payload) == prior["digest"]:
                    return  # Idempotent ACK only; never refreshes last_seen/session/latches.
                raise Rejected(409)
            if prior and sample.collected_at - prior["collected"] < policy.min_interval_seconds:
                raise Rejected(429)
            evaluation = restore_evaluation(prior, self.session)
            evaluation.ingest(sample, policy)
            db.execute(
                "INSERT INTO latest VALUES(?,?,?,?,?,?,?) ON CONFLICT(node) DO UPDATE SET collected=excluded.collected,digest=excluded.digest,payload=excluded.payload,evaluation=excluded.evaluation,session=excluded.session,received=excluded.received",
                (
                    node_id,
                    sample.collected_at,
                    digest(payload),
                    payload,
                    evaluation_state(evaluation),
                    self.session,
                    now,
                ),
            )
            db.execute(
                "INSERT INTO history VALUES(?,?,?,?)",
                (node_id, sample.collected_at, payload, evaluation.status),
            )
            db.execute(
                "DELETE FROM history WHERE collected<?", (now - self.config.history_seconds,)
            )
            db.execute(
                "DELETE FROM history WHERE node=? AND collected NOT IN (SELECT collected FROM history WHERE node=? ORDER BY collected DESC LIMIT ?)",
                (node_id, node_id, self.config.history_per_node),
            )

    def node_view(self, db, node_id, now):
        node = self.config.nodes[node_id]
        row = latest(db, node_id)
        payload = Metrics.model_validate_json(row["payload"]).model_dump() if row else None
        if row and (
            payload["collected_at"] != row["collected"] or digest(row["payload"]) != row["digest"]
        ):
            raise ValueError("stored sample integrity")
        age = now - row["collected"] if row else None
        enabled = node.enabled and self.config.sites[node.site_id].enabled
        fresh = (
            enabled
            and row is not None
            and row["session"] == self.session
            and 0 <= age < node.health_policy.sample_ttl_seconds
        )
        freshness = (
            "disabled"
            if not enabled
            else "never"
            if not row
            else "fresh"
            if fresh
            else "restored"
            if row["session"] != self.session
            else "stale"
        )
        state = (
            restore_evaluation(row, self.session).status
            if fresh
            else "OFFLINE"
            if enabled and age is not None and age >= node.offline_after_seconds
            else "UNKNOWN"
        )
        return dict(
            site_id=node.site_id,
            node_id=node_id,
            node_type=node.node_type,
            enabled=enabled,
            last_seen=row["received"] if row else None,
            status=state,
            metrics=payload if fresh else None,
            historical_metrics=payload if payload is not None and not fresh else None,
            freshness=freshness,
            age_seconds=age,
            health_policy=node.health_policy.model_dump(),
        )

    def inventory(self, site_id, now):
        with self.store.transaction() as db:
            self.checked_clock(db, now)
            nodes = [
                self.node_view(db, n, now)
                for n in self.config.nodes
                if self.config.nodes[n].site_id == site_id
            ]
            return SiteView(
                site_id=site_id,
                status=aggregate([n["status"] for n in nodes if n["enabled"]]),
                nodes=[NodeView.model_validate(n) for n in nodes],
            ).model_dump()

    def snapshot(self, device_id, now):
        identity = self.config.devices[device_id]
        with self.store.transaction() as db:
            self.checked_clock(db, now)
            nodes = [
                self.node_view(db, n, now)
                for n in self.config.nodes
                if self.config.nodes[n].site_id in identity.site_ids
                and self.config.nodes[n].enabled
                and self.config.sites[self.config.nodes[n].site_id].enabled
            ]
            # Age itself is not a new representation; transitions/fresh sample are.
            fingerprint = digest(
                encode([{k: v for k, v in n.items() if k != "age_seconds"} for n in nodes])
            )
            old = db.execute(
                "SELECT revision,fingerprint,body,session FROM snapshots WHERE device=?",
                (device_id,),
            ).fetchone()
            if (
                old
                and old[1] == fingerprint
                and old[3] == self.session
                and now < Snapshot.model_validate_json(old[2]).expires_at
            ):
                return old[2].encode()
            revision = old[0] + 1 if old else 1
            if revision > 2147483647:
                raise ValueError("snapshot revision exhausted")
            counts = dict(healthy=0, warning=0, critical=0, unknown=0)
            for n in nodes:
                counts[
                    {"HEALTHY": "healthy", "WARNING": "warning", "CRITICAL": "critical"}.get(
                        n["status"], "unknown"
                    )
                ] += 1
            if not nodes:
                counts["unknown"] = 1  # M2 control placeholder, not an inventory node.
            status = aggregate([n["status"] for n in nodes])
            order = {"CRITICAL": 0, "WARNING": 1, "OFFLINE": 2, "UNKNOWN": 3, "HEALTHY": 4}
            ordered = sorted(nodes, key=lambda n: (order[n["status"]], n["node_id"]))
            alerts = []
            expires = (
                min(
                    n["metrics"]["collected_at"]
                    + self.config.nodes[n["node_id"]].health_policy.sample_ttl_seconds
                    for n in nodes
                )
                if nodes and all(n["metrics"] is not None for n in nodes)
                else now + self.config.control_ttl_seconds
            )
            for n in nodes:
                if n["metrics"]:
                    expires = min(
                        expires,
                        n["metrics"]["collected_at"]
                        + self.config.nodes[n["node_id"]].health_policy.sample_ttl_seconds,
                    )
                elif (
                    n["age_seconds"] is not None
                    and n["age_seconds"] < self.config.nodes[n["node_id"]].offline_after_seconds
                ):
                    expires = min(
                        expires,
                        now
                        + self.config.nodes[n["node_id"]].offline_after_seconds
                        - n["age_seconds"],
                    )
            for n in ordered[:2]:
                label = (
                    "DATOS VIGENTES"
                    if n["freshness"] == "fresh"
                    else "DATOS HISTORICOS"
                    if n["historical_metrics"]
                    else "SIN MUESTRA"
                )
                alerts.append(
                    Alert(
                        title=self.config.nodes[n["node_id"]].display_name + " " + n["status"],
                        detail=label,
                    )
                )
            if not nodes:
                alerts = [Alert(title="SIN NODOS HABILITADOS", detail="ESTADO DESCONOCIDO")]
            snapshot = Snapshot(
                schema_version=1,
                device_id=device_id,
                revision=revision,
                simulated=False,
                generated_at=now,
                expires_at=expires,
                status=status,
                counts=Counts(**counts),
                alerts=alerts,
            )
            body = encode(snapshot.model_dump())
            db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?) ON CONFLICT(device) DO UPDATE SET revision=excluded.revision,fingerprint=excluded.fingerprint,body=excluded.body,session=excluded.session",
                (device_id, revision, fingerprint, body, self.session),
            )
            return body.encode()
