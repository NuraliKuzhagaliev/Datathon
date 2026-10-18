"""Synthetic subprocess probe; no model, footage or network access."""

import json
import multiprocessing as mp
import os
import subprocess
import sys

from cashproof.lifecycle import bind_worker_lifetime


def child():
    bind_worker_lifetime()
    descendant = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    print(json.dumps({"worker": os.getpid(), "descendant": descendant.pid}), flush=True)
    descendant.wait()


if __name__ == "__main__":
    process = mp.get_context("spawn").Process(target=child)
    process.start()
    process.join()
