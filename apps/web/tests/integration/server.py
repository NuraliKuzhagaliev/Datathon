"""Loopback-only integration harness. Imports A's unchanged production API,
store, pipeline, decoder, preview and export; injects A's scripted TEST model.
Never use this harness for competition footage, deployment or accuracy claims.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

parser = argparse.ArgumentParser()
parser.add_argument('--backend', type=Path, required=True)
parser.add_argument('--frontend', type=Path, required=True)
parser.add_argument('--data', type=Path, required=True)
parser.add_argument('--scenario', choices=['positive', 'negative', 'failed'], default='positive')
args = parser.parse_args()
root = args.backend.resolve()
sys.path[:0] = [str(root / 'services/backend/src'), str(root / 'services/backend/tests')]

from cashproof.api import create_app
from cashproof.config import Settings
from cashproof.jobs import Store
from cashproof.inference.pipeline import Pipeline
from cashproof.media import preview
from cashproof.errors import ProcessingError
from conftest import registry as registry_fixture
from test_media_pipeline import ScriptedSyntheticModel
from synthetic_clip import create
import uvicorn

args.data.mkdir(parents=True, exist_ok=True)
registry = registry_fixture.__wrapped__(args.data)
clip = create(args.data / 'synthetic.mov', rotated=True)
settings = Settings(data_dir=args.data / 'cases', rules_path=registry.path,
                    frontend_dir=args.frontend.resolve(), operator_key=os.environ['CASHPROOF_TEST_KEY'],
                    jury_key=os.environ['CASHPROOF_TEST_JURY_KEY'], mode='server')


class SyntheticWorker:
    ready = True
    model_version = 'scripted-test-only-no-AI'

    def __init__(self):
        self.stop = threading.Event()
        self.store = Store(settings.data_dir)

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=5)

    def run(self):
        while not self.stop.wait(.05):
            claimed = self.store.claim()
            if not claimed:
                continue
            job, _ = claimed
            # Ensure that the browser observes genuine pending state before completion.
            if self.stop.wait(.8):
                return
            if args.scenario == 'failed':
                self.store.fail(job, 'RESOURCE_EXHAUSTED')
                continue
            directory = self.store.directory(job)
            try:
                detail, timeline = Pipeline(ScriptedSyntheticModel(positive=args.scenario == 'positive'), registry).run(
                    directory / 'input.mov', directory, job, time.time() + 60,
                    lambda **changes: self.store.update(job, **changes))
                self.store.update(job, **detail, status='done', stage='complete', progress_percent=100)
                mapping = preview(directory / 'input.mov', directory / 'preview.mp4', timeline, time.time() + 30)
                self.store.update(job, media_ready=True, time_map=mapping)
            except ProcessingError as error:
                if self.store.get(job)['status'] == 'processing':
                    self.store.fail(job, error.code)
            except Exception:
                if self.store.get(job)['status'] == 'processing':
                    self.store.fail(job, 'PROCESSING_FAILED')


class Server(uvicorn.Server):
    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if self.started:
            print(json.dumps({'event': 'synthetic_integration_ready', 'port': sockets[0].getsockname()[1], 'clip': str(clip.resolve())}), flush=True)


if __name__ == '__main__':
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    app = create_app(settings, SyntheticWorker())
    # No production substitution exists: this script alone constructs the injected worker.
    Server(uvicorn.Config(app, log_level='warning', access_log=False)).run(sockets=[sock])
