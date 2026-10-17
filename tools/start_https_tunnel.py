"""Temporary user-authorized Cloudflare HTTPS route; never logs case content."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
BINARY_SHA256 = "4d2490e74082c5d48dbfedaf92576fa5bd1702379ab88eb7faa0cfbe8dc891b6"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloudflared", type=Path, required=True)
    parser.add_argument(
        "--data-dir", type=Path, default=ROOT / "runtime-data/team-server/tunnel"
    )
    args = parser.parse_args()
    binary = args.cloudflared.resolve()
    if hashlib.sha256(binary.read_bytes()).hexdigest() != BINARY_SHA256:
        raise ValueError("Unexpected cloudflared 2026.10.1 executable")
    directory = args.data_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    status = directory / "technical-status.json"
    if status.exists():
        raise RuntimeError("Preserve the existing tunnel; inspect its owned PID first")
    with httpx.Client(timeout=5, trust_env=False) as client:
        response = client.get("http://127.0.0.1:8000/health/ready")
        response.raise_for_status()
        if response.json() != {
            "ready": True,
            "mode": "server",
            "contract_version": "1.0.0",
        }:
            raise RuntimeError("The real team service is not ready")
    command = [
        str(binary),
        "tunnel",
        "--url",
        "http://127.0.0.1:8000",
        "--protocol",
        "http2",
        "--metrics",
        "127.0.0.1:0",
        "--no-autoupdate",
        "--loglevel",
        "info",
    ]
    started = time.monotonic()
    with (
        (directory / "stdout.log").open("w", encoding="utf-8") as stdout,
        (directory / "stderr.log").open("w", encoding="utf-8") as stderr,
    ):
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            cwd=directory,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    try:
        endpoint = None
        while time.monotonic() - started < 120:
            if process.poll() is not None:
                raise RuntimeError("Tunnel exited; inspect the private technical log")
            text = (directory / "stderr.log").read_text(
                encoding="utf-8", errors="replace"
            )
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
            if match:
                endpoint = match.group()
                with httpx.Client(timeout=8, trust_env=False) as client:
                    try:
                        response = client.get(endpoint + "/health/ready")
                        if response.status_code == 200 and response.json() == {
                            "ready": True,
                            "mode": "server",
                            "contract_version": "1.0.0",
                        }:
                            break
                    except (httpx.TransportError, ValueError):
                        pass
            time.sleep(1)
        else:
            raise TimeoutError("Temporary HTTPS readiness was not verified")
        receipt = {
            "url": endpoint,
            "pid": process.pid,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "startup_sec": time.monotonic() - started,
            "binary_sha256": BINARY_SHA256,
            "version": "2026.10.1",
            "origin": "http://127.0.0.1:8000",
            "protocol": "http2",
            "public_health_verified": True,
            "temporary": True,
            "uptime_guaranteed": False,
            "organizer_approval_recorded": False,
            "authorization": "Human explicitly requested this temporary relay after disclosure",
        }
        status.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps(receipt))
    except BaseException:
        process.terminate()
        process.wait(timeout=10)
        raise


if __name__ == "__main__":
    main()
