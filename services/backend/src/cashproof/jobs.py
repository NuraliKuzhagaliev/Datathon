"""Small durable queue. Every state/result transition is a SQLite transaction."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid
from .errors import MESSAGES


def now():
    return datetime.now(timezone.utc).isoformat()


class QueueFull(Exception):
    pass


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "jobs.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
                  state TEXT NOT NULL, owner TEXT NOT NULL, detail TEXT NOT NULL,
                  claimed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS reviews (
                  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                  event_id TEXT NOT NULL, value TEXT NOT NULL,
                  PRIMARY KEY(job_id,event_id));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(
        self,
        filename: str,
        owner: str,
        max_pending: int,
        model_version: str,
        registry_version: str,
    ):
        job = uuid.uuid4().hex
        detail = dict(
            job_id=job,
            filename=Path(filename.replace("\\", "/")).name[:255],
            created_at=now(),
            status="processing",
            stage="queued",
            progress_percent=None,
            elapsed_sec=0,
            duration_sec=None,
            model_result=None,
            error=None,
            events=[],
            coverage=[],
            media_ready=False,
            time_map=[],
            rule_registry_version=registry_version,
            model_version=model_version,
            input_sha256=None,
            is_synthetic=False,
            rules=[],
            review_cues=[],
        )
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute(
                "SELECT count(*) FROM jobs WHERE state='processing'"
            ).fetchone()[0]
            if count >= max_pending:
                raise QueueFull()
            self.directory(job).mkdir()
            # Reservation precedes streaming, so simultaneous uploads cannot oversubscribe.
            db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?,0)",
                (
                    job,
                    time.time(),
                    time.time(),
                    "processing",
                    owner,
                    json.dumps(detail),
                ),
            )
        return job

    def directory(self, job):
        if len(job) != 32 or any(x not in "0123456789abcdef" for x in job):
            raise KeyError(job)
        return self.root / job

    def get(self, job):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job,)).fetchone()
            if row is None:
                raise KeyError(job)
            detail = json.loads(row["detail"])
            detail["elapsed_sec"] = max(
                0,
                (row["updated"] if row["state"] != "processing" else time.time())
                - row["created"],
            )
            reviews = {
                r["event_id"]: json.loads(r["value"])
                for r in db.execute("SELECT * FROM reviews WHERE job_id=?", (job,))
            }
            for event in detail["events"]:
                if event["event_id"] in reviews:
                    event["review"] = reviews[event["event_id"]]
            return detail

    def owner(self, job):
        with self.connect() as db:
            row = db.execute("SELECT owner FROM jobs WHERE id=?", (job,)).fetchone()
            if not row:
                raise KeyError(job)
            return row[0]

    def update(self, job, **changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT detail,state FROM jobs WHERE id=?", (job,)
            ).fetchone()
            if row is None:
                raise KeyError(job)
            value = json.loads(row["detail"])
            if row["state"] != "processing" and any(
                k not in {"media_ready", "time_map"} for k in changes
            ):
                raise ValueError("Automated result is immutable")
            value.update(changes)
            db.execute(
                "UPDATE jobs SET detail=?,state=?,updated=? WHERE id=?",
                (
                    json.dumps(value, ensure_ascii=False, allow_nan=False),
                    value["status"],
                    time.time(),
                    job,
                ),
            )

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id,created FROM jobs WHERE state='processing' AND claimed=0 AND json_extract(detail,'$.input_sha256') IS NOT NULL ORDER BY created LIMIT 1"
            ).fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET claimed=1 WHERE id=?", (row[0],))
            return row[0], row[1]

    def recover(self):
        with self.connect() as db:
            ids = [
                r[0] for r in db.execute("SELECT id FROM jobs WHERE state='processing'")
            ]
        for job in ids:
            self.fail(job, "WORKER_RESTARTED")

    def expire_queued(self, watchdog_sec):
        with self.connect() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM jobs WHERE state='processing' AND claimed=0 AND created<?",
                    (time.time() - watchdog_sec,),
                )
            ]
        for job in ids:
            self.fail(job, "DEADLINE_EXCEEDED")

    def recover_claimed(self):
        with self.connect() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM jobs WHERE state='processing' AND claimed=1"
                )
            ]
        for job in ids:
            self.fail(job, "WORKER_RESTARTED")

    def fail(self, job, code):
        self.update(
            job,
            status="failed",
            stage="failed",
            progress_percent=None,
            error={
                "code": code,
                "message": MESSAGES.get(code, MESSAGES["PROCESSING_FAILED"]),
            },
        )

    def list(self):
        with self.connect() as db:
            ids = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM jobs ORDER BY created DESC LIMIT 200"
                )
            ]
        return [self.get(job) for job in ids]

    def summaries(self):
        with self.connect() as db:
            rows = db.execute("""SELECT id,state,json_extract(detail,'$.filename') AS filename,
                json_extract(detail,'$.created_at') AS created_at,
                json_extract(detail,'$.model_result.verdict') AS verdict
                FROM jobs ORDER BY created DESC LIMIT 200""").fetchall()
        return [
            dict(
                job_id=r["id"],
                filename=r["filename"],
                created_at=r["created_at"],
                status=r["state"],
                verdict=r["verdict"],
            )
            for r in rows
        ]

    def pending_previews(self):
        with self.connect() as db:
            return [
                row[0]
                for row in db.execute(
                    "SELECT id FROM jobs WHERE state='done' AND json_extract(detail,'$.media_ready')=0"
                )
            ]

    def review(self, job, event_id, decision, note):
        if not any(e["event_id"] == event_id for e in self.get(job)["events"]):
            raise KeyError(event_id)
        value = dict(event_id=event_id, decision=decision, note=note, updated_at=now())
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO reviews VALUES(?,?,?)",
                (job, event_id, json.dumps(value)),
            )
        return value

    def delete(self, job):
        import shutil

        # Caller must ensure terminal state. Files are generated paths, never user paths.
        self.get(job)
        with self.connect() as db:
            db.execute("DELETE FROM jobs WHERE id=?", (job,))
        shutil.rmtree(self.directory(job), ignore_errors=True)


def owner_id(key: str):
    return hashlib.sha256(key.encode()).hexdigest()
