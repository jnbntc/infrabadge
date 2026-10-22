"""Explicit opt-in process. Does not install services or configure any network."""

import argparse
import os
import ssl
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from .api import create_app
from .config import CoreConfig
from .core import Core
from .edge import Edge, EdgeConfig, upstream_client
from .private import private_bytes, read_json
from .store import Store, backup_file, restore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("core", "edge", "backup", "restore", "migrate", "check"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cert", type=Path)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    os.umask(0o077)
    store = None
    try:
        if os.geteuid() == 0:
            raise ValueError("normal user required")
        if args.mode in ("restore", "backup"):
            (restore if args.mode == "restore" else backup_file)(args.database, args.output)
            print('{"component":"distributed","event":"backup_or_restore_completed"}')
            return 0
        if args.mode in ("core", "migrate", "check"):
            if args.mode == "check" and (args.database is None or not args.database.is_file()):
                raise ValueError("existing database required")
            store = Store(args.database, migrate=args.mode == "migrate")
            if args.mode == "core":
                app = create_app(Core(CoreConfig.model_validate(read_json(args.config)), store))
            else:
                pass
            if args.mode != "core":
                print('{"component":"distributed","event":"storage_checked"}')
                return 0
        else:
            config = EdgeConfig.model_validate(read_json(args.config))
            credential = private_bytes(config.credential_file, 128).decode("ascii").strip()

            @asynccontextmanager
            async def lifespan(app):
                async with upstream_client(config) as client:
                    app.state.edge = Edge(config, client, credential)
                    yield

            async def dispatch(scope, receive, send):
                await app.state.edge(scope, receive, send)

            app = Starlette(routes=[Mount("/", app=dispatch)], lifespan=lifespan)
        if not 1024 <= args.port <= 65535:
            raise ValueError("unprivileged port required")
        private_bytes(args.key, 16384)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(args.cert, args.key)
        server_config = uvicorn.Config(
            app,
            host=args.bind,
            port=args.port,
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
        )
        server_config.load()
        server_config.ssl.minimum_version = ssl.TLSVersion.TLSv1_2
        uvicorn.Server(server_config).run()
        return 0
    except Exception:
        print('{"component":"distributed","event":"unavailable"}')
        return 1
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
