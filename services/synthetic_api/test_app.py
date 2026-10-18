"""Offline tests: provider responses mocked; only generated public media used."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app as module  # noqa: E402


@pytest.fixture
def api(monkeypatch):
    app = importlib.reload(module)
    monkeypatch.setenv("SYNTHETIC_API_KEY", "test-only-laboratory-key")
    monkeypatch.delenv("GEMINI_LIVE_ENABLED", raising=False)
    with TestClient(app.app) as client:
        yield app, client


AUTH = {"X-API-Key": "test-only-laboratory-key"}


def wait(client, job_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        row = client.get(f"/api/synthetic/jobs/{job_id}", headers=AUTH).json()
        if row["status"] != "processing":
            return row
        time.sleep(0.02)
    pytest.fail("Synthetic processing timed out")


@pytest.mark.parametrize("scenario,expected", [
    ("near_line_start", [1.5]), ("forward", [3.0]), ("reverse", []),
    ("repeated", [2.0, 8.0]), ("early", [1.0]), ("late", [5.0]),
    ("near_miss", []), ("stationary_overlap", []),
])
def test_server_recomputes_all_eight_without_provider(api, monkeypatch, scenario, expected):
    app, client = api
    def forbidden(*args, **kwargs):
        pytest.fail("Recorded mode must not call Gemini")
    monkeypatch.setattr(app, "api_json", forbidden)
    response = client.post("/api/synthetic/jobs", json={"scenario": scenario}, headers=AUTH)
    assert response.status_code == 202
    row = wait(client, response.json()["job_id"])
    assert row["status"] == "done", row
    assert row["result"]["geometry_result"]["event_times_sec"] == expected
    assert row["result"]["new_gemini_requests"] == 0
    if scenario == "near_line_start":
        assert row["result"]["raw_gemini_result"]["event_times_sec"] == []


def test_auth_uploads_unknown_inputs_and_expiry(api):
    app, client = api
    for key in (None, "wrong"):
        headers = {} if key is None else {"X-API-Key": key}
        assert client.post("/api/synthetic/jobs", json={"scenario": "forward"}, headers=headers).status_code == 401
    assert client.post("/api/synthetic/jobs", json={"scenario": "../../private"}, headers=AUTH).status_code == 422
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "url": "https://example.com/video"}, headers=AUTH).status_code == 422
    assert client.post("/api/v1/analyze", json={}, headers=AUTH).status_code == 403
    assert client.post("/api/v1/analyze", files={"file": ("synthetic.mp4", b"fake")}, headers=AUTH).status_code == 415
    assert client.post("/api/synthetic/jobs", content=b"x"*1025, headers=AUTH).status_code == 413
    assert client.get("/api/synthetic/jobs/old-instance", headers=AUTH).status_code == 410
    assert client.get("/media/unknown.mp4").status_code == 404
    assert client.get("/health/ready").json()["jury_analysis_ready"] is False


def enable(app, monkeypatch, age=0):
    key = "fake-provider-key"
    monkeypatch.setenv("GEMINI_API_KEY", key)
    monkeypatch.setenv("GEMINI_LIVE_ENABLED", "1")
    monkeypatch.setenv("GEMINI_FREE_TIER_RECEIPT", json.dumps({
        "checked_at_utc": (datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
        "billing_tier": "Free tier", "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
        "verified_in_google_ai_studio": True, "max_spend_usd": 0}))


def test_live_fails_closed_without_fresh_free_verification(api, monkeypatch):
    app, client = api
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH).status_code == 503
    enable(app, monkeypatch, age=1801)
    assert client.get("/health/ready").json()["gemini_live_ready"] is False
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH).status_code == 503
    assert app.LIVE_CALLS == 0


def test_live_provider_payload_and_separate_geometry(api, monkeypatch):
    app, client = api
    enable(app, monkeypatch)
    calls = []
    def provider(client, method, route, key, payload):
        calls.append(route)
        assert route == "/models/gemini-2.5-flash:generateContent"
        assert "expected" not in json.dumps(payload)
        assert "reference_event_times" not in json.dumps(payload)
        # Confidently wrong predictions must remain visible. Pixel measurements
        # are an independent synthetic baseline, not a claimed model correction.
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({"frame_sides": ['right'] * len(app.CATALOG['near_line_start']['frames'])})}]}}]}
    monkeypatch.setattr(app, "api_json", provider)
    response = client.post("/api/synthetic/jobs", json={"scenario": "near_line_start", "engine": "gemini"}, headers=AUTH)
    row = wait(client, response.json()["job_id"])
    assert row["status"] == "done", row
    assert row["result"]["new_gemini_requests"] == 1
    assert row["result"]["raw_gemini_result"]["event_times_sec"] == []
    assert row["result"]["geometry_result"]["event_times_sec"] == [1.5]
    assert len(row["result"]["geometry_observations"]) == len(app.CATALOG['near_line_start']['frames'])
    assert len(calls) == 1
    app.LIVE_CALLS = 8
    assert client.get("/health/ready").json()["gemini_live_ready"] is False


def test_quota_error_halts_without_retry_or_fake_negative(api, monkeypatch):
    app, client = api
    enable(app, monkeypatch)
    calls = []
    def provider(*args, **kwargs):
        calls.append(1)
        raise app.SafeStop("GEMINI_HTTP_429_NO_RETRY_OR_PAID_FALLBACK")
    monkeypatch.setattr(app, "api_json", provider)
    response = client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH)
    row = wait(client, response.json()["job_id"])
    assert row["status"] == "failed" and "result" not in row
    assert "429" in row["error"]["code"]
    assert app.HALTED and len(calls) == 1
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward", "engine": "gemini"}, headers=AUTH).status_code == 503


def test_busy_and_public_console(api):
    app, client = api
    app.BUSY = True
    assert client.post("/api/synthetic/jobs", json={"scenario": "forward"}, headers=AUTH).status_code == 429
    for route in ("/", "/console.js", "/console.css", "/media/forward.mp4"):
        assert client.get(route).status_code == 200
    response = client.get("/health/live")
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"
