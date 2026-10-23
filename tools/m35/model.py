"""Offline design model. Synthetic fixtures only; NOT a firmware/wire decoder."""

import math
import re

VIEWS = ("global", "home", "work", "mobile", "node", "alerts", "stale", "ambient")
STATES = ("HEALTHY", "WARNING", "CRITICAL", "UNKNOWN", "OFFLINE")
ORDER = {"CRITICAL": 0, "WARNING": 1, "OFFLINE": 2, "UNKNOWN": 3, "HEALTHY": 4}


def aggregate(states):
    if "CRITICAL" in states:
        return "CRITICAL"
    if "WARNING" in states:
        return "WARNING"
    if not states or any(s in ("UNKNOWN", "OFFLINE") for s in states):
        return "OFFLINE" if states and all(s == "OFFLINE" for s in states) else "UNKNOWN"
    return "HEALTHY"


def validate(data):
    if set(data) != {
        "prototype_version",
        "synthetic",
        "now",
        "clock_trusted",
        "transport_ok",
        "nodes",
        "environment",
    }:
        raise ValueError("prototype fields")
    if data["prototype_version"] != 0 or data["synthetic"] is not True:
        raise ValueError("synthetic prototype only")
    if type(data["now"]) is not int or not 1577836800 <= data["now"] <= 4102444800:
        raise ValueError("UTC")
    if any(type(data[k]) is not bool for k in ("clock_trusted", "transport_ok")):
        raise ValueError("flags")
    nodes = data["nodes"]
    if not isinstance(nodes, list) or len(nodes) > 3:
        raise ValueError("bounded fixture inventory")
    seen = set()
    for node in nodes:
        if set(node) != {
            "id",
            "name",
            "site",
            "kind",
            "state",
            "collected_at",
            "cpu",
            "ram",
            "disk",
            "temperature",
        }:
            raise ValueError("node fields")
        if (
            not isinstance(node["id"], str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,23}", node["id"])
            or node["id"] in seen
        ):
            raise ValueError("node identity")
        seen.add(node["id"])
        if not isinstance(node["name"], str) or not re.fullmatch(r"[A-Z0-9 -]{1,18}", node["name"]):
            raise ValueError("display label")
        if (
            node["site"] not in ("home", "work")
            or node["kind"] not in ("server", "mobile")
            or node["state"] not in STATES
        ):
            raise ValueError("scope or state")
        if node["collected_at"] is not None and type(node["collected_at"]) is not int:
            raise ValueError("sample timestamp")
        for key in ("cpu", "ram", "disk", "temperature"):
            value = node[key]
            low, high = (-40, 125) if key == "temperature" else (0, 100)
            if value is not None and (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError("metric range")
    env = data["environment"]
    if env is not None:
        if (
            set(env) != {"collected_at", "temperature", "humidity", "crc_ok"}
            or type(env["collected_at"]) is not int
            or type(env["crc_ok"]) is not bool
        ):
            raise ValueError("local sample")
        for key, low, high in (("temperature", -40, 125), ("humidity", 0, 100)):
            if (
                type(env[key]) not in (int, float)
                or not math.isfinite(env[key])
                or not low <= env[key] <= high
            ):
                raise ValueError("environment range")
    return data


def node_state(node, data):
    at = node["collected_at"]
    if not data["clock_trusted"] or at is None or at > data["now"]:
        return "UNKNOWN"
    age = data["now"] - at
    if age >= 360:
        return "OFFLINE"
    if age >= 180 or any(node[k] is None for k in ("cpu", "ram", "disk")):
        return "UNKNOWN"
    return node["state"]


def age_label(node, data):
    if (
        not data["clock_trusted"]
        or node["collected_at"] is None
        or node["collected_at"] > data["now"]
    ):
        return "EDAD N/D"
    age = data["now"] - node["collected_at"]
    return "EDAD 0MIN" if age < 60 else f"EDAD {min(age // 60, 999)}MIN"


def metrics(node):
    return [
        f"CPU {node['cpu']:.0f}%  RAM {node['ram']:.0f}%",
        f"DISCO {node['disk']:.0f}% USADO",
        "TEMP CPU N/A" if node["temperature"] is None else f"TEMP CPU {node['temperature']:.1f} C",
    ]


def page(data, view):
    validate(data)
    if view not in VIEWS:
        raise ValueError("view")
    titles = dict(
        global_="INFRAESTRUCTURA",
        home="SITIO CASA",
        work="SITIO TRABAJO",
        mobile="MOVILES",
        node="DETALLE NODO",
        alerts="ALERTAS PRIORITARIAS",
        stale="VIGENCIA DE DATOS",
        ambient="AMBIENTE LOCAL",
    )
    title = titles["global_" if view == "global" else view]
    if view == "ambient":
        env = data["environment"]
        valid = (
            env is not None
            and env["crc_ok"]
            and data["clock_trusted"]
            and 0 <= data["now"] - env["collected_at"] < 180
        )
        return (
            title,
            "SHTC3 OK" if valid else "SIN MUESTRA",
            (
                [
                    f"TEMPERATURA {env['temperature']:.1f} C",
                    f"HUMEDAD {env['humidity']:.1f}%",
                    "SENSOR DEL BADGE / SIM",
                    "NO ES TEMPERATURA DE CPU",
                ]
                if valid
                else ["SHTC3 SIN LECTURA VALIDA", "SIN VALORES ACTUALES"]
            ),
        )
    if not data["clock_trusted"]:
        return (
            title,
            "UNKNOWN",
            ["RELOJ NO SINCRONIZADO", "VIGENCIA NO VERIFICABLE", "SIN METRICAS ACTUALES"],
        )
    if not data["transport_ok"]:
        return (
            title,
            "OFFLINE",
            ["GATEWAY NO DISPONIBLE", "SALUD REMOTA NO VERIFICADA", "SIN METRICAS ACTUALES"],
        )
    nodes = data["nodes"]
    if view in ("home", "work"):
        nodes = [n for n in nodes if n["site"] == view]
    if view == "mobile":
        nodes = [n for n in nodes if n["kind"] == "mobile"]
    if view == "node":
        nodes = nodes[:1]
    states = [node_state(n, data) for n in nodes]
    status = aggregate(states)
    if not nodes:
        return (
            title,
            "UNKNOWN",
            ["SIN NODOS INCORPORADOS", "NO CONFIGURADO", "NO EQUIVALE A HEALTHY"],
        )
    if view == "global":
        counts = [states.count(k) for k in ("HEALTHY", "WARNING", "CRITICAL")]
        return (
            title,
            status,
            [
                f"NODOS {len(nodes)}  OK {counts[0]}",
                f"AVISOS {counts[1]}  CRITICOS {counts[2]}",
                f"SIN DATOS {states.count('UNKNOWN') + states.count('OFFLINE')}",
                f"CASA / {sum(n['site'] == 'home' for n in nodes)} NODOS DEMO",
                "TRABAJO / NO CONFIGURADO",
            ],
        )
    if view in ("node", "mobile"):
        n = nodes[0]
        current = node_state(n, data) in ("HEALTHY", "WARNING", "CRITICAL")
        return (
            title,
            status,
            [
                n["name"],
                *(
                    metrics(n)
                    if current
                    else ["DATOS CADUCADOS O AUSENTES", "SIN METRICAS ACTUALES"]
                ),
                age_label(n, data),
            ],
        )
    if view == "alerts":
        ordered = sorted(nodes, key=lambda n: (ORDER[node_state(n, data)], n["id"]))
        lines = []
        for n in ordered:
            state = node_state(n, data)
            if state != "HEALTHY":
                lines += [n["name"] + " " + state, age_label(n, data)]
        return title, status, lines[:6] or ["SIN ALERTAS ACTIVAS"]
    lines = []
    for n in nodes:
        lines += [n["name"] + " " + node_state(n, data), age_label(n, data)]
    if view == "stale":
        lines += ["HISTORICO NO ES ACTUAL"]
    return title, status, lines


class Navigation:
    """Proposed awake BOOT behavior only. No GPIO, USB or power control."""

    def __init__(self):
        self.view = 0
        self.raw = False
        self.stable = False
        self.armed = True
        self.changed = 0
        self.started = 0

    def wake(self, boot_held, now):
        self.raw = self.stable = boot_held
        self.armed = not boot_held
        self.changed = self.started = now

    def sample(self, button, pressed, now, awake=True):
        if button != "BOOT" or not awake:
            return None
        if pressed != self.raw:
            self.raw, self.changed = pressed, now
        if pressed == self.stable or now - self.changed < 30:
            return None
        self.stable = pressed
        if pressed:
            self.started = now
            return None
        event = None
        if self.armed:
            if now - self.started >= 1200:
                self.view, event = 0, "home"
            else:
                self.view, event = (self.view + 1) % len(VIEWS), "next"
        self.armed = True
        return event
