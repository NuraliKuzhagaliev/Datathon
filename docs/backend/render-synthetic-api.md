# Render synthetic cloud laboratory

This is a separate, lightweight cloud experiment. It does not replace the frozen
bank/jury API, run the private dataset, or establish bank-event detection quality.
Only the eight checked-in, regenerated MP4 fixtures are accepted, by scenario ID.
No video upload, user prompt, remote URL or private footage input is available.

## Deployment

Public console/API base: https://cashproof-synthetic-api.onrender.com

The primary site `https://cashproof-web.vercel.app/#synthetic-lab` now has a
cloud mode. It forwards only `/api/synthetic/*` to this Render service using an
external Vercel rewrite; `/api/v1/*` and `/api/ui/*` are not redirected here.
`GET /api/synthetic/session` authenticates the laboratory key and returns live
readiness. The UI keeps that key only in component memory, never browser storage,
cookies or URLs. The Gemini key remains in Render. The main result is the raw
Gemini event list; independent geometry is collapsed into a separate diagnostic.
The browser validates the selected source hash, scenario, job ID and engine.
Changing scenario or leaving aborts waiting, not the server's already accepted job.

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

`GEMINI_MODEL` explicitly selects `gemini-2.5-flash` (default),
`gemini-2.5-flash-lite` or the separately free-tier-verified
`gemini-3.1-flash-lite`. There is **no automatic fallback**.
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

Recorded mode uses captured Gemini frame-side predictions. Independently, the
server decodes the checked-in source and measures **every sampled frame** using
pixel geometry. Live mode sends only sampled synthetic frames to Gemini before
the same independent baseline. Both preserve raw model output separately from
pixel measurements. A fresh Flash Lite cloud test missed the near-line start;
measuring only model-labelled 'on' frames cannot detect confident model errors.
The full-frame baseline is a synthetic geometry algorithm, not an improved VLM
and not a method for detecting banking violations. Do not report its score as
Gemini accuracy.
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

## Model-only synthetic diagnostics

The new 3.1 Flash Lite baseline with the original frame-side prompt completed
8/8 fresh requests: raw events passed 7/8 within 0.5 seconds, missing the start
close to the line. Expected times are used only for scoring after inference.
This is a small development suite, not a generalization or banking-accuracy claim.

`GEMINI_PROMPT_PROFILE` selects `frame-sides-v3`, `center-sides-v6` or experimental
`temporal-witness-v5`;
authenticated experiment requests may explicitly select either `profile`.
The v5 experiment uses uniform 2 fps source PTS plus the final source frame, a
fixed camera crop enlarged beside context, and explicit source frame IDs. It
does not find candidates using pixel geometry. The model chooses crossing,
before and after frame IDs plus direction; the server validates their existence,
time order and witness interval, then maps IDs to original timestamps. No
geometric event result or reference time is given to the model or substituted
into the raw result. Cropped model-input panels are not original evidence.

The v5 live probe was rejected: only 1/3 completed model event lists passed,
including a wrong direction, followed by one provider HTTP 503 technical failure.
It is not the default. The v6 candidate keeps unmodified source images, tightens
the center/overlap distinction and enables HIGH thinking on Gemini 3.1; model
event timing still comes only from model observations and source PTS.

The v6 probe also missed the near-line start, then stopped on provider HTTP 503;
there were no retries. A final `native-video-v7` comparison uses only the bundled
MP4, explicit 4 fps video metadata, and model-reported before/event/after times.
It validates direction and temporal consistency without changing model times.
The initial 3.8 configuration was rejected because a project Free Tier badge
alone did not prove model-specific prices. Official Standard Free Tier input
and output prices and AI Studio model quotas were then verified; a separate
fresh key-bound $0 model-price gate was tested. Approval then succeeded.
The full 3.8 / native-reference-v11 run passed 8/8 target event lists and times,
with TP5/TN3/FP0/FN0. Its all-direction inventory passed 7/8: it omitted the
reverse return in the repeated clip. See [comparison](gemini-cloud-comparison.md).

The selected `native-reference-v12-review` uses the same first-pass input and
prompt. If several target events are reported, one bounded second model call
checks the intervening return on the original timeline. It is a distinct
verification stage, not an automatic retry. All calls count toward the cap of
eight per instance; `new_gemini_requests` is 1 or 2. Model-returned times are
never replaced with geometry. Inconsistent or missing return evidence fails
explicitly rather than inventing a crossing. The visible red reference overlay
is disclosed and preserves every source PTS; both input hashes are exported.

The main site uses only `/api/synthetic/*` on this Render service. Both old
Vercel project-level Cloudflare routing rules were disabled and published.
The primary UI supports authenticated jobs, polling, source-time seeking,
raw model results and JSON export. The existing real-video API is disabled.

Official model/pricing references checked on 18 October 2026:
https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite and
https://ai.google.dev/gemini-api/docs/pricing .
