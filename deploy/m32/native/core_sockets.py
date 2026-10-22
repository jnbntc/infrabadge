"""Existing pilot adapter, parameterized for publication; one Core and Store, two FDs."""

import argparse
import ipaddress
import os
import socket
import ssl
from pathlib import Path

import uvicorn
from infrabadge_gateway.distributed.api import create_app
from infrabadge_gateway.distributed.config import CoreConfig
from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.private import private_bytes, read_json
from infrabadge_gateway.distributed.store import Store


def inherited_sockets(addresses, port):
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "2":
        raise ValueError("exact socket activation required")
    result = []
    try:
        for fd in (3, 4):
            sock = socket.socket(fileno=fd)
            result.append(sock)
            if (
                sock.family != socket.AF_INET
                or sock.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM
                or sock.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1
            ):
                raise ValueError("listening IPv4 TCP socket required")
            sock.set_inheritable(False)
        if {s.getsockname() for s in result} != {(v, port) for v in addresses}:
            raise ValueError("unexpected listening address")
        for key in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES"):
            os.environ.pop(key, None)
        return result
    except BaseException:
        for sock in result:
            sock.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--listener", action="append", required=True)
    parser.add_argument("--port", type=int, default=9443)
    args = parser.parse_args()
    os.umask(0o077)
    store = None
    sockets = []
    try:
        if os.geteuid() == 0:
            raise ValueError("normal user required")
        addresses = args.listener
        if (
            len(addresses) != 2
            or addresses[0] != "127.0.0.1"
            or len(set(addresses)) != 2
            or not 1024 <= args.port <= 65535
        ):
            raise ValueError("explicit two-address configuration required")
        if any(
            ipaddress.IPv4Address(a).is_unspecified or ipaddress.IPv4Address(a).is_multicast
            for a in addresses
        ):
            raise ValueError("unicast required")
        sockets = inherited_sockets(addresses, args.port)
        config = CoreConfig.model_validate(read_json(args.config))
        private_bytes(args.key, 16384)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        store = Store(args.database)
        app = create_app(Core(config, store))
        server_config = uvicorn.Config(
            app,
            ssl_certfile=str(args.cert),
            ssl_keyfile=str(args.key),
            ssl_version=ssl.PROTOCOL_TLS_SERVER,
            access_log=False,
            log_level="critical",
            proxy_headers=False,
            server_header=False,
            limit_concurrency=16,
            h11_max_incomplete_event_size=8192,
            timeout_keep_alive=2,
            workers=1,
            reload=False,
        )
        server_config.load()
        server_config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
        server = uvicorn.Server(server_config)
        server.run(sockets=sockets)
        return 0 if server.started else 1
    except Exception:
        print('{"component":"core_socket_adapter","event":"unavailable"}', flush=True)
        return 1
    finally:
        if store is not None:
            store.close()
        for sock in sockets:
            sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
