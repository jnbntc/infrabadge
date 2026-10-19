import argparse
import json
from pathlib import Path
import uvicorn
from .app import create_app
from .models import GatewayConfig

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--cert', type=Path, required=True)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8443)
    args = parser.parse_args()
    try:
        config = GatewayConfig.model_validate_json(args.config.read_text())
        if args.key.stat().st_mode & 0o077:
            raise ValueError('private key permissions')
    except (OSError, ValueError):
        parser.error('invalid private configuration/key; contents are not logged')
    uvicorn.run(create_app(config), host=args.host, port=args.port, ssl_certfile=str(args.cert),
                ssl_keyfile=str(args.key), access_log=False, log_level='warning')

if __name__ == '__main__': main()
