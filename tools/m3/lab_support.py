"""Temporary loopback HTTPS, using new ephemeral credentials. No host services."""

import contextlib
import hashlib
import secrets
import socket
import ssl
import subprocess
import threading
import time

import httpx
import uvicorn
from infrabadge_gateway.app import create_app
from infrabadge_gateway.lab import certificates
from infrabadge_gateway.models import GatewayConfig


@contextlib.contextmanager
def loopback(folder, clock=time.time, certificate_kind="valid"):
    ca, cert, key = certificates(folder, kind=certificate_kind)
    collector_token, device_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    token = folder / "collector.token"
    token.write_text(collector_token)
    token.chmod(0o600)

    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    config = GatewayConfig.model_validate(
        {
            "devices": {
                "badge-lab": {"node_id": "workstation", "token_sha256": [digest(device_token)]}
            },
            "collectors": {
                "workstation": {
                    "display_name": "WORKSTATION",
                    "token_sha256": [digest(collector_token)],
                }
            },
        }
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(config, clock=clock),
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
            lifespan="off",
            access_log=False,
            log_level="critical",
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not server.started:
            raise RuntimeError("loopback_start_failed")
        yield (
            {
                "node_id": "workstation",
                "gateway_url": "https://localhost:" + str(listener.getsockname()[1]),
                "ca_file": str(ca),
                "timeout_seconds": 3,
            },
            token,
            device_token,
        )
    finally:
        server.should_exit = True
        thread.join(5)
        listener.close()
        if thread.is_alive():
            raise RuntimeError("loopback_cleanup_failed")


@contextlib.contextmanager
def container_loopback(folder, image):
    """Explicit opt-in rootless smoke; transient container, loopback port only."""
    import json

    gateway = folder / "gateway"
    gateway.mkdir(mode=0o700)
    ca, cert, key = certificates(gateway)
    collector_token, device_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    token = folder / "collector.token"  # NOT mounted in gateway container
    token.write_text(collector_token)
    token.chmod(0o600)
    config = {
        "devices": {
            "badge-lab": {
                "node_id": "workstation",
                "token_sha256": [hashlib.sha256(device_token.encode()).hexdigest()],
            }
        },
        "collectors": {
            "workstation": {
                "display_name": "WORKSTATION",
                "token_sha256": [hashlib.sha256(collector_token.encode()).hexdigest()],
            }
        },
    }
    (gateway / "gateway.json").write_text(json.dumps(config))
    (gateway / "gateway.json").chmod(0o600)
    name = "ib-m3-smoke-" + secrets.token_hex(6)

    def podman(*arguments, check=True):
        return subprocess.run(
            ["podman", *arguments], capture_output=True, text=True, check=check, timeout=30
        )

    started = False
    try:
        podman(
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "--userns=keep-id:uid=10001,gid=10001",
            "--user=10001:10001",
            "--cap-drop=all",
            "--security-opt=no-new-privileges",
            "--read-only",
            "--log-driver=none",
            "-p",
            "127.0.0.1::8443",
            "-v",
            str(gateway) + ":/run/infrabadge:ro,Z",
            image,
        )
        started = True
        port = int(podman("port", name, "8443/tcp").stdout.strip().rsplit(":", 1)[1])
        url = "https://localhost:" + str(port)
        with httpx.Client(
            verify=ssl.create_default_context(cafile=str(ca)), trust_env=False, timeout=1
        ) as client:
            ready = False
            for _ in range(40):
                try:
                    ready = (
                        client.get(
                            url + "/api/v1/devices/badge-lab/status",
                            headers={"Authorization": "Bearer " + device_token},
                        ).status_code
                        == 200
                    )
                except httpx.TransportError:
                    pass
                if ready:
                    break
                time.sleep(0.1)
            if not ready:
                raise RuntimeError("container_gateway_not_ready")
        yield (
            {
                "node_id": "workstation",
                "gateway_url": url,
                "ca_file": str(ca),
                "timeout_seconds": 3,
            },
            token,
            device_token,
        )
    finally:
        if started:
            removed = podman("stop", "--time", "3", name, check=False)
            if removed.returncode != 0:
                podman("rm", "-f", name)
            if podman("container", "exists", name, check=False).returncode == 0:
                raise RuntimeError("container_cleanup_failed")
