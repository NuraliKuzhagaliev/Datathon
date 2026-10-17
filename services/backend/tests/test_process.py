"""Real TCP/bootstrap checks; no model or fixture verdict is substituted."""

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import httpx


def test_dynamic_port_and_actual_unready_model(tmp_path):
    root = Path(__file__).resolve().parents[3]
    env = os.environ | {
        "PYTHONPATH": str(root / "services/backend/src"),
        "CASHPROOF_API_KEY": "test-process-key-" + "x" * 32,
        "CASHPROOF_MODE": "offline",
        "CASHPROOF_MODEL_DIR": str(tmp_path / "absent-model"),
        "CASHPROOF_RULES": str(root / "assets/rules/registry.json"),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "cashproof.bootstrap",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
            "--data-dir",
            str(tmp_path / "persistent cases"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    lines = queue.Queue()
    threading.Thread(
        target=lambda: lines.put(process.stdout.readline()), daemon=True
    ).start()
    try:
        value = json.loads(lines.get(timeout=25))
        assert (
            set(value) == {"event", "port"}
            and value["event"] == "http_ready"
            and value["port"] > 0
        )
        base = f"http://127.0.0.1:{value['port']}"
        with httpx.Client(timeout=3, trust_env=False) as client:
            assert client.get(base + "/health/live").json() == {"status": "ok"}
            ready = client.get(base + "/health/ready")
            assert ready.status_code == 503 and ready.json()["ready"] is False
            assert client.get(base + "/api/ui/cases").status_code == 401
            assert client.get(
                base + "/api/ui/cases", headers={"X-API-Key": env["CASHPROOF_API_KEY"]}
            ).json() == {"items": []}
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
