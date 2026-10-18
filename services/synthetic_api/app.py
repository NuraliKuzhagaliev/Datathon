"""Cloud experiment: bundled synthetic media ONLY; not the jury detector.

No upload/file/URL input, local weights, torch, retries, or paid fallback.
Results and request counters are ephemeral on Render Free. Export results before
idle/redeploy. A fresh key-bound Free Tier receipt is required for live Gemini.
"""

import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import time

import av
import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict
from typing import Literal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from gemini_synthetic_smoke import (  # noqa: E402
    PROMPT_V2, PROMPT_V3, PROMPT_V4, SCHEMA_V2, SafeStop, api_json, events_from_sides, ordered_frames,
    validate_result, verify_free_tier,
)
from synthetic_geometry import measure_side  # noqa: E402
from services.synthetic_api.observations import (  # noqa: E402
    PROMPT as WITNESS_PROMPT, SCHEMA as WITNESS_SCHEMA, parse_witnesses, visual_input,
)

ASSETS = REPO / "apps/web/public/synthetic-demo"
CATALOG = {c["id"]: c for c in json.loads(
    (ASSETS / "recordings.json").read_text(encoding="utf-8"))["cases"]}
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PROFILE = os.getenv("GEMINI_PROMPT_PROFILE", "frame-sides-v3")
JOBS: dict[str, dict] = {}
TASKS: set = set()
BUSY = False
LIVE_CALLS = 0
LAST_CALL = 0.0
HALTED = False
BOOT_ID = secrets.token_hex(8)
KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class ModelResponseError(SafeStop):
    def __init__(self, code, body):
        super().__init__(code)
        self.model_text = "".join(p.get("text", "") for c in body.get("candidates", [])[:1]
                                  for p in c.get("content", {}).get("parts", [])
                                  if not p.get("thought"))[:32768]


def live_guard():
    if MODEL not in ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"):
        raise SafeStop("MODEL_NOT_IN_VERIFIED_FREE_ALLOWLIST")
    if os.getenv("GEMINI_LIVE_ENABLED") != "1" or HALTED:
        raise SafeStop("LIVE_DISABLED_OR_HALTED_NO_RETRY")
    key = os.getenv("GEMINI_API_KEY", "")
    try:
        receipt = json.loads(os.getenv("GEMINI_FREE_TIER_RECEIPT", "{}"))
        verify_free_tier(receipt, key)
    except (ValueError, KeyError, TypeError):
        raise SafeStop("FRESH_FREE_TIER_VERIFICATION_REQUIRED") from None
    if not key or LIVE_CALLS >= 8:
        raise SafeStop("LIVE_REQUEST_BUDGET_EXHAUSTED")
    return key


def authenticate(key=Depends(KEY_HEADER)):
    expected = os.getenv("SYNTHETIC_API_KEY", "")
    if not expected or not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "Invalid synthetic API key")


@asynccontextmanager
async def lifespan(app):
    yield
    for task in TASKS:
        task.cancel()
    if TASKS:
        await asyncio.gather(*TASKS, return_exceptions=True)


app = FastAPI(title="CashProof synthetic cloud laboratory", version="0.1.0",
              description="Synthetic blue-square/red-line experiments only. Not a bank violation API.",
              lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware,
    allow_origins=["https://cashproof-web.vercel.app"],
    allow_methods=["GET", "POST"], allow_headers=["X-API-Key", "Content-Type"])


@app.middleware("http")
async def headers(request, call_next):
    # Never accept video bytes or arbitrary prompts, even on unknown routes.
    if request.method in ("POST", "PUT", "PATCH"):
        size = request.headers.get("content-length", "0")
        if not size.isdigit() or int(size) > 1024:
            return JSONResponse({"detail": "Only small scenario selections accepted"}, 413)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "Video uploads are disabled"}, 415)
        # Bound chunked bodies too, before FastAPI buffers/parses them.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 1024:
                return JSONResponse({"detail": "Request too large"}, 413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; media-src 'self'; img-src 'self' data:; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
    return response


@app.get("/")
def index():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/console.js")
def console():
    return FileResponse(Path(__file__).with_name("console.js"), media_type="text/javascript")


@app.get("/console.css")
def styles():
    return FileResponse(Path(__file__).with_name("console.css"), media_type="text/css")


@app.get("/health/live")
def health():
    return {"status": "ok", "synthetic_only": True, "local_pc_required": False}


@app.get("/health/ready")
@app.get("/api/synthetic/health")
def ready():
    reason = None
    try:
        live_guard()
    except SafeStop as exc:
        reason = str(exc)
    return {"synthetic_only": True, "recorded_replay_ready": True,
            "gemini_live_ready": reason is None, "gemini_block_reason": reason,
            "model": MODEL, "live_requests_started_this_instance": LIVE_CALLS,
            "prompt_profile": PROFILE,
            "max_live_requests_this_instance": 8, "results_ephemeral": True,
            "jury_analysis_ready": False, "boot_id": BOOT_ID}


@app.get("/api/synthetic/session", dependencies=[Depends(authenticate)])
def session():
    return ready()


@app.get("/api/synthetic/scenarios")
def scenarios():
    return {"synthetic_only": True, "scenarios": [
        {"id": c["id"], "title": c["title_ru"], "duration_sec": c["duration_sec"],
         "video_url": f"/media/{c['id']}.mp4"} for c in CATALOG.values()]}


@app.get("/media/{scenario}.mp4")
def media(scenario: str):
    if scenario not in CATALOG:
        raise HTTPException(404, "Unknown synthetic scenario")
    return FileResponse(ASSETS / f"{scenario}.mp4", media_type="video/mp4")


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str
    engine: Literal["recorded", "gemini"] = "recorded"
    profile: Literal["frame-sides-v3", "temporal-witness-v5", "center-sides-v6", "native-video-v7", "native-video-v8-high", "native-video-v9-high"] | None = None


def analyze(selection):
    global LIVE_CALLS, LAST_CALL, HALTED
    row = CATALOG[selection.scenario]
    path = ASSETS / f"{selection.scenario}.mp4"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != row["video_sha256"]:
        raise SafeStop("BUNDLED_SYNTHETIC_HASH_MISMATCH")
    profile = (selection.profile or PROFILE) if selection.engine == "gemini" else "frame-sides-v3"
    if profile not in ("frame-sides-v3", "temporal-witness-v5", "center-sides-v6", "native-video-v7", "native-video-v8-high", "native-video-v9-high"):
        raise SafeStop("UNRECOGNIZED_SYNTHETIC_PROMPT_PROFILE")
    native = profile.startswith("native-video-")
    prompt = PROMPT_V2 if native else WITNESS_PROMPT if profile == "temporal-witness-v5" else PROMPT_V4 if profile == "center-sides-v6" else PROMPT_V3
    if profile == "native-video-v9-high":
        prompt += "\nFor each reported crossing at time t, use before_time_sec=t-0.25 and after_time_sec=t+0.25. Both must lie inside the video. Check those actual nearby moments and their center sides. Keep all crossings sorted and event_times_sec exactly equal to left_to_right crossing times. Return numeric seconds, not strings. A completed pass has one center crossing even while the square overlaps red for several frames.\n"
    parts, sampled = visual_input(path) if profile == "temporal-witness-v5" else ordered_frames(path)
    frames = [{"frame_id": f["frame_id"], "timestamp_sec": f["timestamp_sec"]}
              for f in sampled]  # Scoring labels are never detector inputs.
    if profile != "temporal-witness-v5" and frames != row["frames"]:
        raise SafeStop("RECORDED_SOURCE_TIMELINE_MISMATCH")
    model_version = "recorded-gemini-2.5-flash"
    if selection.engine == "gemini":
        if native:
            parts = [{"inlineData": {"mimeType": "video/mp4", "data": base64.b64encode(path.read_bytes()).decode()}, "videoMetadata": {"fps": 4}}]
        delay = max(0, 13 - (time.monotonic() - LAST_CALL))
        if delay:
            time.sleep(delay)
        key = live_guard()  # Recheck receipt after any wait and before every call.
        LIVE_CALLS += 1
        LAST_CALL = time.monotonic()
        try:
            with httpx.Client(timeout=120, follow_redirects=False, trust_env=False) as client:
                body = api_json(client, "POST", f"/models/{MODEL}:generateContent", key, {
                    "contents": [{"role": "user", "parts": [*parts, {"text": prompt}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 8192 if native or profile == "center-sides-v6" else 4096,
                        "responseMimeType": "application/json",
                        "responseSchema": SCHEMA_V2 if native else WITNESS_SCHEMA if profile == "temporal-witness-v5" else {"type": "OBJECT", "properties": {"frame_sides": {
                            "type": "ARRAY", "minItems": len(frames), "maxItems": len(frames),
                            "items": {"type": "STRING", "enum": ["left", "on", "right"]}}},
                            "required": ["frame_sides"]},
                        **({"mediaResolution": "MEDIA_RESOLUTION_HIGH"} if profile in ("native-video-v8-high", "native-video-v9-high") else {}),
                        **({"thinkingConfig": {"thinkingBudget": 1024}}
                           if MODEL.startswith("gemini-2.5-") else
                           {"thinkingConfig": {"thinkingLevel": "HIGH"}}
                           if profile == "center-sides-v6" else {})}})
            try:
                raw = parse_witnesses(body, frames) if profile == "temporal-witness-v5" else validate_result(body, row["duration_sec"], witnesses=native, frames=None if native else frames)
            except SafeStop as exc:
                raise ModelResponseError(str(exc), body) from None
            model_version = body.get("modelVersion", MODEL)
        except Exception:
            HALTED = True  # Never automatically retry/resume after a provider failure.
            raise
    else:
        raw = events_from_sides({"frame_sides": row["gemini_sides"]}, frames)
    # Independent synthetic baseline: measure every sampled source frame. A VLM
    # can be confidently wrong, so limiting this check to its 'on' labels misses
    # those errors. This is explicitly pixel geometry, never model accuracy.
    needed = {round(f["timestamp_sec"], 6): i for i, f in enumerate(frames)}
    sides, measurements = [None] * len(frames), []
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            pts = round(float(frame.pts * frame.time_base), 6)
            if pts not in needed:
                continue
            index = needed.pop(pts)
            measured = measure_side(frame.to_ndarray(format="rgb24"))
            sides[index] = measured["side"]
            measurements.append({**frames[index], "model_side": raw.get("frame_sides", [None] * len(frames))[index], **measured})
    if needed:
        raise SafeStop("SOURCE_FRAME_NOT_FOUND")
    result = events_from_sides({"frame_sides": sides}, frames)
    return {"synthetic_only": True, "engine": selection.engine,
            "new_gemini_requests": int(selection.engine == "gemini"),
            "model_version": model_version, "source_sha256": digest,
            "prompt_version": profile,
            "geometry_method": "independent_pixel_measurement_of_every_sampled_source_frame",
            "raw_gemini_result": raw, "geometry_result": result,
            "geometry_observations": measurements, "frames": frames,
            "disclaimer": "Independent blue-square/red-line geometry. Does not establish Gemini accuracy or detect bank violations."}


async def run_job(job_id, selection):
    global BUSY
    start = time.monotonic()
    try:
        result = await asyncio.to_thread(analyze, selection)
        JOBS[job_id].update(status="done", result=result)
    except ModelResponseError as exc:
        JOBS[job_id].update(status="failed", error={"code": str(exc)},
                           model_diagnostic={"synthetic_only": True, "raw_model_text": exc.model_text})
    except SafeStop as exc:
        JOBS[job_id].update(status="failed", error={"code": str(exc)})
    except Exception:
        # Never return provider payloads, headers, stack traces or secrets.
        JOBS[job_id].update(status="failed", error={"code": "SYNTHETIC_ANALYSIS_FAILED"})
    finally:
        JOBS[job_id]["elapsed_sec"] = round(time.monotonic() - start, 3)
        BUSY = False


@app.post("/api/synthetic/jobs", status_code=202, dependencies=[Depends(authenticate)])
async def submit(selection: Selection):
    global BUSY
    if selection.scenario not in CATALOG:
        raise HTTPException(422, "Only bundled synthetic scenarios are allowed")
    if BUSY:
        raise HTTPException(429, "One synthetic job at a time", headers={"Retry-After": "15"})
    if selection.engine == "gemini":
        try:
            live_guard()
        except SafeStop as exc:
            raise HTTPException(503, str(exc)) from None
    # Bound RAM and keep completed results at most 24 hours; no paid datastore.
    now = time.time()
    for jid in list(JOBS):
        if now - JOBS[jid]["created_unix"] > 86400:
            del JOBS[jid]
    if len(JOBS) >= 64:
        del JOBS[next(iter(JOBS))]
    job_id = BOOT_ID + "-" + secrets.token_hex(16)
    JOBS[job_id] = {"job_id": job_id, "status": "processing", "created_unix": now,
                    "scenario": selection.scenario, "engine": selection.engine}
    BUSY = True
    task = asyncio.create_task(run_job(job_id, selection))
    TASKS.add(task)
    task.add_done_callback(TASKS.discard)
    return {"job_id": job_id}


@app.get("/api/synthetic/jobs/{job_id}", dependencies=[Depends(authenticate)])
def job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(410, "Result absent or expired after restart; never treated as negative")
    return JOBS[job_id]


@app.post("/api/v1/analyze", dependencies=[Depends(authenticate)])
def jury_disabled():
    raise HTTPException(403, "Real-video jury analysis disabled; synthetic laboratory only")
