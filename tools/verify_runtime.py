"""Real local API verification with optional Python socket isolation.

Private results/logs are never printed. Only aggregate technical metadata is safe
for coding-agent consumption. The server and its own worker tree are terminated.
"""

import argparse
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import time
import httpx

ROOT = Path(__file__).resolve().parents[1]
GUARD = """import ipaddress,socket
_connect=socket.socket.connect
_connect_ex=socket.socket.connect_ex
_resolve=socket.getaddrinfo
def _allowed(host):
    if host=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False
def _guard_connect(self,address):
    if isinstance(address,tuple) and not _allowed(address[0]):raise OSError('External network disabled in verification process')
    return _connect(self,address)
def _guard_connect_ex(self,address):
    if isinstance(address,tuple) and not _allowed(address[0]):raise OSError('External network disabled in verification process')
    return _connect_ex(self,address)
def _guard_resolve(host,*args,**kwargs):
    if host is not None and not _allowed(host):raise OSError('External DNS disabled in verification process')
    return _resolve(host,*args,**kwargs)
socket.socket.connect=_guard_connect
socket.socket.connect_ex=_guard_connect_ex
socket.getaddrinfo=_guard_resolve
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--model-dir", type=Path, default=ROOT / "models/Qwen3-VL-2B-Instruct"
    )
    p.add_argument("--bundle", type=Path)
    p.add_argument("--concurrency", type=int, choices=range(1, 6), default=1)
    p.add_argument("--deny-external-network", action="store_true")
    a = p.parse_args()
    a.output = a.output.resolve()
    a.output.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    root = a.bundle.resolve() if a.bundle else ROOT
    python = root / "python/python.exe" if a.bundle else Path(sys.executable)
    source = root / "app" if a.bundle else root / "services/backend/src"
    prefix = []
    launch_env = {}
    cwd = root
    if a.bundle:
        from jsonschema import validate

        launch = json.loads((root / "launch.json").read_text(encoding="utf-8"))
        validate(
            launch,
            json.loads(
                (ROOT / "packages/contracts/desktop-launch.schema.json").read_text()
            ),
        )
        python = (root / launch["executable"]).resolve()
        cwd = (root / launch["cwd"]).resolve()
        if not python.is_relative_to(root) or not cwd.is_relative_to(root):
            raise ValueError("Unsafe desktop launch paths")
        prefix = launch["args_prefix"]
        launch_env = launch["env"]
    paths = [str((cwd / launch_env.get("PYTHONPATH", str(source))).resolve())]
    if a.deny_external_network:
        guard = a.output / "guard"
        guard.mkdir(exist_ok=True)
        (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
        paths.insert(0, str(guard))
    env = (
        os.environ
        | launch_env
        | {
            "PYTHONPATH": os.pathsep.join(paths),
            "CASHPROOF_API_KEY": key,
            "CASHPROOF_JURY_KEY": "",
            "CASHPROOF_MODE": "offline",
            "CASHPROOF_MAX_PENDING": str(a.concurrency),
            "CASHPROOF_MODEL_DIR": str(
                (root / "models/Qwen3-VL-2B-Instruct")
                if a.bundle
                else a.model_dir.resolve()
            ),
            "CASHPROOF_RULES": str(root / "assets/rules/registry.json"),
            "PYTHONNOUSERSITE": "1",
        }
    )
    if a.bundle:
        env["CASHPROOF_FFMPEG"] = str(root / "bin/ffmpeg.exe")
    ready_lines = queue.Queue()
    start = time.time()
    with (a.output / "private-server-stderr.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                str(python),
                *prefix,
                "-m",
                "cashproof.bootstrap",
                "--host",
                "127.0.0.1",
                "--port",
                "0",
                "--data-dir",
                str(a.output / "cases"),
            ],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(
            target=lambda: ready_lines.put(process.stdout.readline()), daemon=True
        ).start()
        try:
            readiness = json.loads(ready_lines.get(timeout=30))
            base = f"http://127.0.0.1:{readiness['port']}"
            with httpx.Client(timeout=5, trust_env=False) as client:
                while time.time() - start < 180:
                    if process.poll() is not None:
                        raise RuntimeError("Backend exited before model readiness")
                    status = client.get(base + "/health/ready")
                    if status.status_code == 200 and status.json()["ready"]:
                        break
                    time.sleep(0.5)
                else:
                    raise RuntimeError(
                        "Model did not become ready within startup budget"
                    )
            warmup = time.time() - start
            result = subprocess.run(
                [
                    str(Path(sys.executable)),
                    str(ROOT / "tools/benchmark_api.py"),
                    "--base-url",
                    base,
                    "--video",
                    str(a.video.resolve()),
                    "--output",
                    str(a.output / "private-results"),
                    "--concurrency",
                    str(a.concurrency),
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=330,
            )
            if result.returncode:
                (a.output / "private-client-error.log").write_text(
                    result.stderr, encoding="utf-8"
                )
                raise RuntimeError(
                    "Runtime client failed; inspect private technical log locally"
                )
            summary = json.loads(result.stdout.strip().splitlines()[-1])
            summary.update(
                startup_sec=warmup,
                python_external_network_denied=a.deny_external_network,
                portable_bundle=bool(a.bundle),
            )
            (a.output / "technical-summary.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            print(json.dumps(summary))
        finally:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
