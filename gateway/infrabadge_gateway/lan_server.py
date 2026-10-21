"""Candidate M3.1 single-process gateway with two TLS entrances. Opt-in only."""

import argparse
import asyncio
import contextlib
import os
import signal
import socket
import ssl
import stat
from pathlib import Path

import uvicorn

from .app import create_app
from .lan_edge import LanEntrance
from .lan_policy import LanPolicy, lease_valid, private_json
from .lan_telemetry import Telemetry
from .models import GatewayConfig


def applications(config, policy, authorized, telemetry):
    local = create_app(config, events=telemetry.emit)
    return local, LanEntrance(local, config, policy, authorized, telemetry)


def tls_config(app, port, cert, key):
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        ssl_certfile=str(cert),
        ssl_keyfile=str(key),
        proxy_headers=False,
        server_header=False,
        access_log=False,
        log_level="critical",
        lifespan="off",
        limit_concurrency=16,
        h11_max_incomplete_event_size=8192,
        timeout_keep_alive=2,
        timeout_graceful_shutdown=5,
    )
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
    return config


def validate_tls(cert, key, ca, hostname):
    """Full local TLS handshake in memory: CA/SAN/dates/key, no network access."""
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = ssl.TLSVersion.TLSv1_2
    server.load_cert_chain(cert, key)
    client = ssl.create_default_context(cafile=ca)
    client.minimum_version = ssl.TLSVersion.TLSv1_2
    for name in ("localhost", hostname):
        incoming, outgoing, peer_in, peer_out = (ssl.MemoryBIO() for _ in range(4))
        left = client.wrap_bio(incoming, outgoing, server_hostname=name)
        right = server.wrap_bio(peer_in, peer_out, server_side=True)
        done = set()
        for _ in range(100):
            for index, endpoint in enumerate((left, right)):
                try:
                    endpoint.do_handshake()
                    done.add(index)
                except ssl.SSLWantReadError:
                    pass
            peer_in.write(outgoing.read())
            incoming.write(peer_out.read())
            if len(done) == 2:
                break
        else:
            raise ValueError("local_tls_validation_failed")


class ManagedServer(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self):
        yield  # One supervisor owns process signal handling for both listeners.


async def serve(configs):
    sockets, servers, tasks = [], [], []
    loop = asyncio.get_running_loop()
    original_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def stop():
        for server in servers:
            server.should_exit = True

    try:
        for config in configs:
            channel = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(channel)
            channel.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            channel.bind((config.host, config.port))
            channel.listen(32)
            channel.setblocking(False)
            servers.append(ManagedServer(config))
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop)
        tasks = [asyncio.create_task(s.serve(sockets=[p])) for s, p in zip(servers, sockets)]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        stop()
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10)
            except TimeoutError:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        for channel in sockets:
            channel.close()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
            signal.signal(sig, original_handlers[sig])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "policy", "lease", "telemetry", "ca", "cert", "key"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if os.geteuid() == 0:
            raise ValueError("non_root_required")
        policy = LanPolicy.load(args.policy)
        config = GatewayConfig.model_validate(private_json(args.config, 65536))
        if config.enable_faults:
            raise ValueError("fault_injection_forbidden_in_lan_deployment")
        if not lease_valid(args.lease, policy):
            raise ValueError("network_not_approved")
        # Read key permissions using the same regular-file/ownership boundary.
        key_info = args.key.stat()
        if (
            args.key.is_symlink()
            or not stat.S_ISREG(key_info.st_mode)
            or key_info.st_uid != os.getuid()
            or key_info.st_mode & 0o077
        ):
            raise ValueError("private_key_permissions")
        validate_tls(args.cert, args.key, args.ca, policy.hostname)
        telemetry = Telemetry(args.telemetry)
        apps = applications(config, policy, lambda: lease_valid(args.lease, policy), telemetry)
        telemetry.emit("gateway_started")
        asyncio.run(
            serve(
                [
                    tls_config(app, port, args.cert, args.key)
                    for app, port in zip(apps, (8443, 8444))
                ]
            )
        )
        return 0
    except Exception:
        print(
            "M3.1 gateway stopped; inspect private inputs. No TLS bypass or automatic network changes."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
