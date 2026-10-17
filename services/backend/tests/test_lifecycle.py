import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import queue
import threading

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows process ownership regression")
def test_owner_crash_terminates_worker_and_descendant():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    env = os.environ | {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    parent = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("lifecycle_probe.py"))],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    handles = []
    try:
        lines = queue.Queue()
        threading.Thread(
            target=lambda: lines.put(parent.stdout.readline()), daemon=True
        ).start()
        line = lines.get(timeout=15)
        assert line, "Lifetime probe did not start"
        pids = json.loads(line)
        for pid in pids.values():
            handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
            assert handle
            handles.append((pid, handle))
        parent.kill()  # Deliberately kill only the owner, without taskkill /T.
        parent.wait(timeout=5)
        for _, handle in handles:
            assert kernel.WaitForSingleObject(handle, 10000) == 0
    finally:
        if parent.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(parent.pid), "/T", "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        for pid, handle in handles:
            if kernel.WaitForSingleObject(handle, 0) != 0:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            kernel.CloseHandle(handle)
