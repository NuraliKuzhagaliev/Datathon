# Gemini synthetic experiment

The owner authorized Gemini API on 18 October 2026, with a strict USD 0 budget
and synthetic video only. This is an isolated opt-in development tool; production
workers, private evaluation inputs, desktop offline mode and public API routing
are not switched to cloud inference.

`tools/gemini_synthetic_smoke.py` reads the ignored `.env.gemini.local` server-side.
It generates H.264 animations with no audio and sends their bytes or locally
decoded original frames directly to the official Google Gemini REST endpoint.
It accepts no input-video path. The original three cases
exercise direction, a negative control, repeated events and source timestamps.
The expected geometric crossing times are used only for scoring, never in the
model prompt. A pass requires correct counts and all time errors at most 0.5 s.
These controls measure no bank-procedure or legal recognition accuracy.

Before use, verify the exact key's project is **Free tier** in Google AI Studio.
The local receipt contains a key fingerprint, observed tier, verification time
and zero-spend restriction. A mismatched key, other tier, missing verification or
receipt older than 30 minutes blocks inference. This is a point-in-time billing
check, not a provider-enforced spending cap. Do not change billing during a run.
The Gemini generation API has no documented `free-only` request parameter.

Only explicit model IDs with documented free input/output tiers are allowed.
Available models are queried before using the explicitly selected model (default
`gemini-2.5-flash`); no paid model, paid upgrade,
grounding/search tools, persistent file upload, batch or explicit cache is used.
Any HTTP failure including 429 stops the run without retries or model fallback.
HTTP redirects are rejected and credentials use a header rather than a URL.
Provider error bodies and raw network exceptions are never printed. Results and
technical token counts are saved alongside the generated animations.

Example using the prepared environment, from the task workspace:

```powershell
work/.venv/Scripts/python.exe outputs/datathon/tools/gemini_synthetic_smoke.py --free-tier-receipt work/gemini-free-tier-receipt.json --output outputs/model-development/gemini-synthetic-free-20261018-1
```

Output directories must be new, preserving earlier attempts. The environment
needs PyAV, Pillow and httpx; the prepared backend test environment already has
these dependencies. No local model or GPU server needs to start.

Free-tier content may be used for Google product improvement. Do not run private
competition footage through this tool. Any broader cloud scope requires resolving
the competition restriction and provider data-handling terms first.

Sources checked 18 October 2026: [pricing](https://ai.google.dev/gemini-api/docs/pricing),
[billing](https://ai.google.dev/gemini-api/docs/billing),
[video inputs](https://ai.google.dev/gemini-api/docs/generate-content/video-understanding),
[data terms](https://ai.google.dev/gemini-api/terms).

## Executed result

The saved key matched a masked key in the observed Google AI Studio project,
which showed **Free tier**. The Spend page also showed Free tier and USD 0.00;
that dashboard is delayed and is not an immediate invoice. No billing changes,
prepayment, paid fallback or real-video requests were made.

Three separate explicitly selected attempts were preserved:

| Model | Actual result |
| --- | --- |
| Gemini 3.8 Flash | Model discovery succeeded; the first video request ended in a network timeout. No detection result. |
| Gemini 2.5 Flash | First video request returned HTTP 503. No detection result. |
| Gemini 2.5 Flash-Lite | All three synthetic video requests completed; 1/3 passed the predeclared direction/count/0.5-second checks. |

Flash-Lite reported 2.5 s for the positive crossing at 3.0 s (0.5 s error,
passes tolerance); incorrectly reported a left-to-right crossing in the reverse
negative; and reported 2/5/8 s instead of 2/8 s on the repeated case, admitting
the reverse crossing at 5 s. Latencies were 3.172, 2.922 and 2.609 seconds.
Decoded generated files have no audio tracks; provider usage metadata nevertheless
includes an AUDIO token category, which is preserved without claiming audio input.
The exact generated inputs, provider results, token counts and source checks are
under the task's `outputs/model-development/gemini-synthetic-free-20261018-*`.

The API connection works, but this tested model is **not qualified** for directional
event detection or bank violations. Neither native-video connectivity nor this
small synthetic score establishes real-data accuracy. The production website,
private evaluation pipeline, local model and tunnel remain stopped/unmodified.
Fifteen guard/response validation tests and Ruff checks passed locally.

## Repeated Flash experiment and selected recipe

The owner requested a fresh free-only Flash test and a corrected direction/time
prompt. The exact key's project was rechecked in AI Studio as Free tier before
the calls; no billing settings were changed. Each attempt retains its own new
output directory, prompt text/hash, actual input hash and successful API responses.
An invalid/inconsistent response is a failed attempt, never a negative verdict.

Native-video `direction-witness-v2` requires before/after observations for every
crossing in both directions, then exact consistency with the selected event list.
Flash completed the positive at 2.75 s versus 3.0 s, but hallucinated an extra
crossing in the reverse clip and contradicted its own selected list. The gate
rejected that response. A separate 1024-thinking-token attempt completed the
positive with 0.5 s error, then hit HTTP 503 on the reverse clip. Gemini 3.8 Flash
also returned 503. None of these interrupted attempts is a completed benchmark.

The selected `frame-sides-v3` asks **only for each frame's observed center side**.
The input is unchanged decoded source pixels at 4 fps, each preceded by its actual
source PTS and frame ID. The parser rejects missing/extra/invalid side observations.
Code derives direction from chronological left/right changes; an on-line sample
counts only once a later frame confirms the opposite side. Times refer to actual
source frames, not a model-generated clock or an annotation. Returning from touching
the line to the original side produces no crossing. Original full-frame inputs
are retained; no source labels, expected side lists or event times enter inference.
Pixel-derived synthetic truth is used only for local scoring and source checks.

The same frozen prompt hash, Flash model, 1024 thinking-token budget and uncropped
input recipe were tested across the original 3, new challenge 4 and boundary 1
cases (8 independent video requests). Results: **7/8 scenarios pass** the declared
count/direction/0.5-second checks; TP4/TN3/FP0/FN1 for synthetic video-level detection.
Five of six requested crossings are found with no extra events. Detected-event
time errors are 0, 0, 0, 0.2 and 0 s; maximum 0.2 s, with one event missed rather
than assigned an error of zero. Latency min/median/max: 2.063/4.922/6.484 s.

The boundary case starts 10 px left of the line and crosses at 1.5 s. Flash labels
its initial centers on-line and misses the event. This was a targeted diagnostic
after the stationary-overlap case exposed incorrect per-frame sides; it is not
an independent held-out test. Across all eight clips, frame sides are 173/208
correct, including 0/24 on the stationary near-line clip despite its correct
negative event result. Stronger midpoint/width wording (`frame-sides-v4`) and a
separate fixed original-pixel detail crop did not repair the boundary failure.
Those attempts are preserved and are **not** the selected defaults.

The CLI now defaults to v3 and 1024 thinking tokens. To reproduce all eight
synthetic scenarios after refreshing the exact-key free-tier receipt:

```powershell
work/.venv/Scripts/python.exe outputs/datathon/tools/gemini_synthetic_smoke.py --free-tier-receipt work/gemini-free-tier-receipt.json --output outputs/model-development/gemini-flash-next-run --model gemini-2.5-flash --prompt frame-sides-v3 --suite extended --thinking-budget 1024
```

These results combine prompt, input representation, reasoning budget and
deterministic temporal logic changes. They do not isolate a prompt-only effect,
establish repeatability across runs, or measure bank-video violation accuracy.
The selected prompt still has an observed boundary miss and is not qualified for
real violations. Private videos, website routing, API contracts and offline
runtime are unchanged. All calls used the verified Free tier with a USD 0 budget,
no paid fallback, and no automatic retries. Thirty-four focused guard, temporal
logic and actual-decode synthetic checks passed; Ruff passed.

The consolidated public receipt is at the task's
`outputs/model-development/GEMINI-FLASH-PROMPT-COMPARISON-20261018.json`.

## Boundary recovery with explicit synthetic pixel geometry

The owner requested recovery of the near-line start miss and a fresh eight-case
free-only run. AI Studio again showed Free tier for the exact saved key. Numeric
bounding-box probes on a single generated image, including a nearest-neighbour
enlargement, still put the square's midpoint on the line. A newer Flash probe
returned 503. These failed attempts remain separate, without a claim of improvement.

`synthetic_geometry.py` now provides an **opt-in hybrid geometry experiment**.
The initial Gemini output stays immutable in `raw_gemini_result`. Only observations
labelled `on` and their immediate neighbours are checked using original decoded
pixels. The checker detects the blue rectangle bounds and the vertical red line,
measures both centers, and replaces an ambiguous side only when that geometry is
visible and unambiguous. It rejects absent/ambiguous references as a technical error.
It uses no scenario name, expected time, scoring side label or fixed x=320 line.
Direction and actual source-frame timestamps then use the existing temporal logic.
Initial `on` followed by `right` alone still never implies a left-to-right event.

This checker is specific to the explicit blue-square/red-line synthetic task.
It does not repair Gemini itself or detect bank violations. It is not enabled in
production. The flag `--refine-geometry` is required; default pure-model recipes
remain reproducible. A model error corrected by pixels is never counted as a
correct raw Gemini prediction. The new tests include shifted line positions,
missing/ambiguous references, unchanged initial-on behavior and removal of all
scoring labels before the boundary recovery test.

All eight stored model responses were replayed with this same correction:
**8/8 passed**, six requested events found, no extra events, exact fixture times
including recovery at 1.5 s. This replay made **zero new API requests** and is
explicitly recorded as `saved_model_response_replay`, not a fresh model run.

A fresh eight-case run then started with the failing boundary case. The first
three cases completed and passed: boundary 1.5 s (raw Gemini missed it), forward
3.0 s and reverse no-event. The fourth, repeated-crossing request returned HTTP
429. The run stopped immediately with no retries or paid fallback. AI Studio's
Free tier rate page showed **20/20 requests per day**. Five fresh cases remain:
repeated, early, late, near_miss and stationary_overlap. Therefore **a fresh 8/8
pass has not been established**. Current live evidence is 3/8 planned cases,
3/3 passed among those completed, with the separate full eight-case replay above.

The remaining cases can be run after refreshing the exact-key Free tier receipt
and after the provider resets the daily free quota:

```powershell
work/.venv/Scripts/python.exe outputs/datathon/tools/gemini_synthetic_smoke.py --free-tier-receipt work/gemini-free-tier-receipt.json --output outputs/model-development/gemini-flash-hybrid-remaining-next-run --model gemini-2.5-flash --prompt frame-sides-v3 --thinking-budget 1024 --refine-geometry --scenarios repeated early late near_miss stationary_overlap
```

Generation starts are spaced at least 13 seconds apart to respect the observed
5-RPM free limit. No automation or automatic resume was started. The current
summary is at `outputs/model-development/GEMINI-SYNTHETIC-BOUNDARY-FIX-20261018.json`;
the fresh run and replay retain separate artifacts. Forty-three local tests and
Ruff passed. Private data and public API routing remain untouched; paid access is
disabled and all executed requests used the verified Free tier.
