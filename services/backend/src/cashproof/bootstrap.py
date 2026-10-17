import argparse
import asyncio
from dataclasses import replace
import ipaddress
import json
import multiprocessing
from pathlib import Path
import socket
import uvicorn
from .config import Settings, force_offline


class Server(uvicorn.Server):
    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if self.started:
            print(
                json.dumps(
                    {"event": "http_ready", "port": sockets[0].getsockname()[1]}
                ),
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description="CashProof local inference service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--frontend-dir", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if args.data_dir:
        settings = replace(settings, data_dir=args.data_dir.resolve())
    if args.frontend_dir:
        settings = replace(settings, frontend_dir=args.frontend_dir.resolve())
    if settings.mode == "offline" and not ipaddress.ip_address(args.host).is_loopback:
        parser.error("Offline mode must bind loopback")
    force_offline()
    from .api import create_app

    app = create_app(settings)
    sock = socket.socket(
        socket.AF_INET6 if ":" in args.host else socket.AF_INET, socket.SOCK_STREAM
    )
    sock.bind((args.host, args.port))
    sock.listen(128)
    sock.setblocking(False)
    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",
        access_log=False,
        timeout_keep_alive=5,
    )
    try:
        asyncio.run(Server(config).serve(sockets=[sock]))
    finally:
        sock.close()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
