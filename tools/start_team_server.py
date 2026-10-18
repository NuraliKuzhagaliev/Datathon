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
from jsonschema import validate
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]


def runtime_plan(bundle=None):
    if bundle is None:
        return (
            [sys.executable],
            ROOT,
            {"PYTHONPATH": str(ROOT / "services/backend/src")},
            None,
        )
    root = Path(bundle).resolve()
    launch = json.loads((root / "launch.json").read_text(encoding="utf-8"))
    validate(
        launch,
        json.loads(
            (ROOT / "packages/contracts/desktop-launch.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    if any(flag not in {"-s", "-B", "-u"} for flag in launch["args_prefix"]):
        raise ValueError("Only supported Python interpreter flags are allowed")
    executable = (root / launch["executable"]).resolve()
    cwd = (root / launch["cwd"]).resolve()
    if not executable.is_relative_to(root) or not cwd.is_relative_to(root):
        raise ValueError("Runtime paths must stay inside the bundle")
    if not executable.is_file() or not cwd.is_dir():
        raise ValueError("Runtime launch paths are missing")
    if any(
        re.search(r"(^|_)(API_?KEY|KEY|TOKEN|SECRET|PASSWORD)($|_)", key, re.I)
        for key in launch["env"]
    ):
        raise ValueError("Bundle environment must not contain credentials")
    manifest = (root / "manifest.json").read_bytes()
    return (
        [str(executable), *launch["args_prefix"]],
        cwd,
        launch["env"],
        hashlib.sha256(manifest).hexdigest(),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--data-dir", type=Path, default=ROOT / "runtime-data/team-server"
    )
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument(
        "--bundle",
        type=Path,
        help="Run the checked portable runtime instead of the development environment",
    )
    args = parser.parse_args()
    runtime_command, runtime_cwd, runtime_env, bundle_manifest_sha256 = runtime_plan(
        args.bundle
    )
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
    env = (
        os.environ
        | runtime_env
        | {
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
    )
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
        *runtime_command,
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
            cwd=runtime_cwd,
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
            "portable_runtime": args.bundle is not None,
            "runtime_manifest_sha256": bundle_manifest_sha256,
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
