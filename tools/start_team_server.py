"""Start the real same-origin integration service; never print credentials."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--data-dir", type=Path, default=ROOT / "runtime-data/team-server"
    )
    parser.add_argument("--ffmpeg", type=Path, required=True)
    args = parser.parse_args()
    directory = args.data_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    frontend = ROOT / "apps/web/dist"
    if not (frontend / "index.html").is_file():
        raise FileNotFoundError("Build the production frontend first")
    credential_file = directory / "credentials.json"
    if not credential_file.exists():
        with credential_file.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "operator": secrets.token_urlsafe(32),
                    "jury": secrets.token_urlsafe(32),
                },
                stream,
            )
    credentials = json.loads(credential_file.read_text(encoding="utf-8"))
    env = os.environ | {
        "PYTHONPATH": str(ROOT / "services/backend/src"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "CASHPROOF_API_KEY": credentials["operator"],
        "CASHPROOF_JURY_KEY": credentials["jury"],
        "CASHPROOF_MODE": "server",
        "CASHPROOF_MAX_PENDING": "1",
        "CASHPROOF_FFMPEG": str(args.ffmpeg.resolve()),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "OTEL_SDK_DISABLED": "true",
    }
    base = f"http://127.0.0.1:{args.port}"
    with httpx.Client(timeout=2, trust_env=False) as client:
        try:
            client.get(base + "/health/live")
        except httpx.TransportError:
            pass
        else:
            raise RuntimeError(
                "Port already serves HTTP; preserve its process and credentials"
            )
    command = [
        sys.executable,
        "-m",
        "cashproof.bootstrap",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--data-dir",
        str(directory / "cases"),
        "--frontend-dir",
        str(frontend),
    ]
    started = time.monotonic()
    with (
        (directory / "stdout.log").open("w", encoding="utf-8") as stdout,
        (directory / "stderr.log").open("w", encoding="utf-8") as stderr,
    ):
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            while time.monotonic() - started < 240:
                if process.poll() is not None:
                    raise RuntimeError(
                        "Service exited; inspect the local technical stderr log"
                    )
                try:
                    response = client.get(base + "/health/ready")
                    health = response.json()
                    if response.status_code == 200 and health == {
                        "ready": True,
                        "mode": "server",
                        "contract_version": "1.0.0",
                    }:
                        assert client.get(base + "/").status_code == 200
                        assert client.get(base + "/api/ui/cases").status_code == 401
                        assert (
                            client.get(
                                base + "/api/ui/cases",
                                headers={"X-API-Key": credentials["operator"]},
                            ).status_code
                            == 200
                        )
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.5)
            else:
                raise TimeoutError("Model warmup exceeded B's 240 second budget")
        result = {
            "base_url": base,
            "pid": process.pid,
            "health": health,
            "startup_sec": time.monotonic() - started,
            "command": command,
            "credentials_saved_locally": True,
            "cross_machine_https_verified": False,
        }
        (directory / "technical-status.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(json.dumps(result))
    except BaseException:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            process.terminate()
        process.wait(timeout=10)
        raise


if __name__ == "__main__":
    main()
