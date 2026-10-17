# Codex B → Codex A: integration requests

Frontend implementation consumes contract 1.0.0 without changing shared files. This is a request log, not evidence that the backend has been integrated.

The concrete joint procedure is now in [INTEGRATION_CHECKLIST.md](INTEGRATION_CHECKLIST.md), with 18 acceptance checks and a result template. [HANDOFF_TO_A.txt](HANDOFF_TO_A.txt) is a concise message prepared for the teammate; it has not been sent. The [three-minute demo](PITCH.md) distinguishes current synthetic rehearsal from a verified model demonstration. B's implementation is published in `codex/frontend` (initial implementation commit `9f3716c`; use the branch's latest revision). A remains the final integrator.

## Verified against A's source

At backend revision `1d10013fbfcff57bd8782077543d5aa4816fab4f`, A's 20 tests passed locally. Three browser scenarios also passed against A's unchanged production API, persistence, pipeline, decoder, preview and export with generated video and A's scripted test model. They cover positive/negative/failure, auth scopes, media playback, review persistence, immutable jury results, ZIP download and intentional synthetic-case deletion. Setup, scope and limitations: [BACKEND_INTEGRATION.md](BACKEND_INTEGRATION.md). This is not a live GPU/model qualification.

After merging, update the A-owned root README from the initial planning status to the actual implementation and qualified release status. The Windows connected build exists; full offline inference still requires A's bundle and a measured disconnected run.

## First real integration

1. Serve `apps/web/dist` and `/api`, `/health` on the same origin. During development the Vite proxy targets `http://127.0.0.1:8000`; override with `CASHPROOF_DEV_BACKEND` in the terminal environment.
2. Provide an operator key through the UI or a private channel, never commit it. `/api/ui/cases` is used to validate the session. Health alone does not authenticate a user.
3. Return every required `CaseDetail` field, including nulls/empty arrays. The frontend validates responses against generated OpenAPI JSON schemas and refuses synthetic responses outside explicit development demo mode.
4. UI events must match immutable `model_result` by `jury_violation_index`, timestamp, job identity and stable event/review ID. Active production rules must exist in the case's rule snapshot.
5. Provide authenticated MP4 preview with `Content-Type: video/mp4` and an explicit, monotonic source/preview `time_map`. Playback does not assume identity mapping. The browser uses authenticated fetch → Blob, never a key in the URL.
6. Return review responses from PUT with the saved event ID and timestamp; review never mutates the jury result. Export returns actual `application/zip`.
7. Keep technical error codes safe. Backend error captions/descriptions must not be forwarded to cloud tooling. Frontend reports status-specific recovery text.

## Desktop bundle

Supply `releases/backend/launch.json` per the frozen schema with relative executable/cwd and interpreter-only args_prefix (for example `["-s"]`). Bundle all model/runtime dependencies before offline use. No baked-in secret environment variables.

Electron appends `-m cashproof.bootstrap --host 127.0.0.1 --port 0 --data-dir <userData>/cases --frontend-dir <resources>/web`, sets random `CASHPROOF_API_KEY`, `CASHPROOF_MODE=offline`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. The earlier B implementation/documentation omitted the fixed module invocation; this has been corrected to match A's published bundle builder.

Emit one newline-terminated JSON stdout line `{"event":"http_ready","port":49152}` after binding. Startup waits up to 60 seconds for HTTP, then up to 240 seconds for `/health/ready` to return ready=true, mode=offline, contract_version=1.0.0. Logs go to stderr; the desktop drains them without showing real-case content.

Full offline packaging intentionally fails if the bundle is missing. A separate connected-only package is available, visibly named CashProof Connected. This does not satisfy the offline inference requirement.

On Windows, Electron terminates only the live child tree it created. The backend must also guarantee worker cleanup if its parent Python process crashes unexpectedly (for example by a Windows Job Object or equivalent worker lifecycle design). Do not leave orphan GPU workers. Normal child-tree shutdown can be exercised by B's synthetic lifecycle test; crash recovery with A's actual worker remains a joint gate.

## Unresolved real-world gates

- No live backend address/key has been supplied to B yet.
- No inference/runtime/model bundle is present in this checkout.
- Real video semantic review and actual source/preview synchronization need local human verification.
- Full offline processing, GPU compatibility, latency, public HTTPS and final merge must be demonstrated on A's machine.

Please expose model readiness honestly. The frozen health response has no model version, GPU info or per-resource readiness fields; the frontend does not invent those values. Model/rule versions are read from completed cases.
