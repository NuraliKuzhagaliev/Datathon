import json
import multiprocessing as mp
import os
import queue
import subprocess
import threading
import time
import sys
from .config import Settings, force_offline
from .errors import ProcessingError
from .jobs import Store
from .rules import Registry
from .media import Timeline, preview


def worker_main(settings: Settings, channel):
    # No request contents, model outputs, exception strings or keys are logged.
    force_offline()
    store = Store(settings.data_dir)
    try:
        from .lifecycle import bind_worker_lifetime

        bind_worker_lifetime()
        from .inference.model import LocalQwen
        from .inference.pipeline import Pipeline

        registry = Registry(settings.rules_path)
        model = LocalQwen(settings.model_dir)
        pipeline = Pipeline(model, registry, settings.max_candidates)
        channel.send(("ready", model.version, bool(registry.enabled)))
    except Exception as error:
        code = (
            "MODEL_NOT_PROVISIONED"
            if isinstance(error, FileNotFoundError)
            else "MODEL_LOAD_FAILED"
        )
        sys.stderr.write(
            json.dumps(
                {
                    "event": "worker_unavailable",
                    "code": code,
                    "exception_type": type(error).__name__,
                }
            )
            + "\n"
        )
        channel.send(("unavailable",))
        return
    while True:
        claimed = store.claim()
        if not claimed:
            time.sleep(0.1)
            continue
        job, created = claimed
        channel.send(("active", job, created))
        directory = store.directory(job)
        model.torch.cuda.reset_peak_memory_stats()
        started = time.time()
        try:
            detail, timeline = pipeline.run(
                directory / "input.mov",
                directory,
                job,
                created + settings.watchdog_sec,
                lambda **changes: store.update(job, **changes),
            )
            # One atomic publication. Preview is handled outside the GPU worker.
            store.update(
                job,
                **detail,
                status="done",
                stage="complete",
                progress_percent=100,
                model_version=model.version,
            )
            channel.send(("done", job))
        except ProcessingError as error:
            store.fail(job, error.code)
        except Exception as error:
            is_oom = isinstance(error, model.torch.OutOfMemoryError)
            store.fail(job, "RESOURCE_EXHAUSTED" if is_oom else "PROCESSING_FAILED")
            if is_oom:
                model.torch.cuda.empty_cache()
        try:
            (directory / "technical-metrics.json").write_text(
                json.dumps(
                    {
                        "peak_vram_bytes": model.torch.cuda.max_memory_allocated(),
                        "worker_sec": time.time() - started,
                        "queue_wait_sec": started - created,
                    }
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
        channel.send(("idle",))


def terminate_owned(process):
    if not process or not process.is_alive():
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        process.terminate()
    process.join(timeout=5)


class Worker:
    def __init__(self, settings):
        self.settings = settings
        self.ready = False
        self.model_version = "unavailable"
        self.stop = threading.Event()
        self.artifacts = queue.Queue()
        self.process = None
        self.active = None

    def start(self):
        # Prevent two servers from recovering/claiming the same durable queue.
        from filelock import FileLock

        self.lock = FileLock(str(self.settings.data_dir / "service.lock"))
        self.lock.acquire(timeout=0)
        self.store = Store(self.settings.data_dir)
        self.store.recover()
        for job in self.store.pending_previews():
            if (self.store.directory(job) / "source-timeline.json").exists():
                self.artifacts.put(job)
        self.thread = threading.Thread(target=self.supervise, daemon=True)
        self.preview_thread = threading.Thread(target=self.make_previews, daemon=True)
        self.thread.start()
        self.preview_thread.start()

    def supervise(self):
        context = mp.get_context("spawn")
        while not self.stop.is_set():
            self.ready = False
            parent, child = context.Pipe(duplex=False)
            self.process = context.Process(
                target=worker_main, args=(self.settings, child), daemon=True
            )
            self.process.start()
            child.close()
            while self.process.is_alive() and not self.stop.wait(0.1):
                self.store.expire_queued(self.settings.watchdog_sec)
                while parent.poll():
                    try:
                        message = parent.recv()
                    except EOFError:
                        break
                    if message[0] == "ready":
                        self.model_version, self.ready = message[1], message[2]
                    elif message[0] == "active":
                        self.active = (message[1], message[2])
                    elif message[0] == "idle":
                        self.active = None
                    elif message[0] == "done":
                        self.artifacts.put(message[1])
                if (
                    self.active
                    and time.time() - self.active[1] > self.settings.watchdog_sec
                ):
                    terminate_owned(self.process)
                    if self.store.get(self.active[0])["status"] == "processing":
                        self.store.fail(self.active[0], "DEADLINE_EXCEEDED")
                    self.active = None
            self.ready = False
            terminate_owned(self.process)
            if self.active:
                if self.store.get(self.active[0])["status"] == "processing":
                    self.store.fail(self.active[0], "WORKER_RESTARTED")
                self.active = None
            self.store.recover_claimed()
            parent.close()
            self.stop.wait(10)

    def make_previews(self):
        while not self.stop.is_set():
            try:
                job = self.artifacts.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                directory = self.store.directory(job)
                timeline = Timeline(
                    **json.loads((directory / "source-timeline.json").read_text())
                )
                mapping = preview(
                    directory / "input.mov",
                    directory / "preview.mp4",
                    timeline,
                    time.time() + 60,
                )
                self.store.update(job, media_ready=True, time_map=mapping)
            except Exception:
                pass  # Optional artifact failure cannot mutate the jury verdict.

    def close(self):
        self.ready = False
        self.stop.set()
        terminate_owned(self.process)
        self.thread.join(timeout=6)
        self.preview_thread.join(timeout=2)
        self.lock.release()
