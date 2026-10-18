# Render synthetic cloud laboratory

This is a separate, lightweight cloud experiment. It does not replace the frozen
bank/jury API, run the private dataset, or establish bank-event detection quality.
Only the eight checked-in, regenerated MP4 fixtures are accepted, by scenario ID.
No video upload, user prompt, remote URL or private footage input is available.

## Deployment

Single Python web service; explicitly select **Free**, one instance, Frankfurt.
No database, disk, worker, paid compute or paid fallback is provisioned. Existing
Render services are untouched. Free instance hours are shared with the workspace.
Use no payment method or a verified zero spend limit for metered workspace usage.

- Repository: `https://github.com/NuraliKuzhagaliev/Datathon`
- Branch: `codex/model-development`
- Build: `pip install -r services/synthetic_api/requirements.txt`
- Start: `python -m uvicorn services.synthetic_api.app:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`
- Python: `3.12.10` (`PYTHON_VERSION` environment variable).
- Health: `/health/live` (no model request or dependency traffic).

Runtime secrets are managed in Render environment variables, never in Git:
`SYNTHETIC_API_KEY` (new dedicated random lab key), `GEMINI_API_KEY` (existing key).
`GEMINI_LIVE_ENABLED=1` permits live experiments only with
`GEMINI_FREE_TIER_RECEIPT`: JSON with the existing experiment's exact key hash,
`billing_tier="Free tier"`, `verified_in_google_ai_studio=true`, `max_spend_usd=0`,
and actual `checked_at_utc`. The key-bound verification expires after **30 minutes**.
Do not renew it without checking the exact key's project in AI Studio. Expiry
disables new Gemini requests; recorded replay remains available without a PC.
There is no provider request flag that guarantees free billing; verified account
tier is a prerequisite, and this deliberately fails closed rather than promising
unlimited free inference. Do not attach billing or change plans.

`GEMINI_MODEL` explicitly selects `gemini-2.5-flash` (default) or the separately
free-tier-verified `gemini-2.5-flash-lite`. There is **no automatic fallback**.
Flash has already exhausted its observed daily quota; Flash Lite can be selected
explicitly for a new synthetic cloud experiment, without claiming Flash's results
transfer to Lite. Both are capped at eight request starts per instance,
one job at a time, at least 13 seconds between request starts, no automatic retry
or model fallback. Any provider exception stops further live requests for that
instance. HTTP 429 is a technical failure, never a successful negative. No
background wakeups or repeated quota probes are installed.

## API

- `GET /` is a small Russian browser console. Enter the lab key in memory only.
- `GET /health/live`, `/health/ready`: process and explicit live/replay readiness.
- `GET /api/synthetic/scenarios`: fixed catalog, generated fixture URLs.
- `POST /api/synthetic/jobs`: `X-API-Key`, JSON
  `{"scenario":"near_line_start","engine":"recorded"}` or `engine:"gemini"`.
  Returns 202 with `job_id`. Extra fields/URLs and arbitrary scenario IDs fail.
- `GET /api/synthetic/jobs/{job_id}`: same key, processing/done/failed result.
- `/api/v1/analyze` rejects real-video analysis. **Not a jury submission endpoint.**

Recorded mode uses captured Gemini frame-side predictions, then actually decodes
the checked-in source on the server and refines ambiguous observations using
pixel geometry. Live mode sends only sampled synthetic frames to Gemini before
the same refinement. Both preserve raw model output separately from correction.
Source hashes and sampled PTS are checked. Expected event times are scoring data,
not detection inputs. `new_gemini_requests` distinguishes the modes explicitly.

Render Free sleeps after inactivity, and may restart at any time. Job data is
ephemeral (RAM), capped at 64 jobs / 24 hours, lost on restart; clients get 410
for missing IDs rather than a made-up result. Download JSON before restart.
This is deliberately not the durable production bank queue. No uptime or
300-second competition qualification is claimed. Do not keep the free service
awake with a synthetic ping loop.

## Offline tests

`python -m pytest services/synthetic_api/test_app.py -q`

Tests run all eight generated fixtures through the server, verify source times,
auth, upload rejection, expiry, concurrency, no live calls in recorded mode,
key-bound free-tier gating, request caps, mocked live output and 429 stop behavior.
These tests do not consume Gemini quota or constitute fresh model accuracy.
