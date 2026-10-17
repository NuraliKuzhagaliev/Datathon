# CashProof shared implementation contract

Version 1.0.0. Prepared for two Codex workstreams on 17 October 2026. This is a build specification, not a claim that the product has been implemented. Read this file before either master prompt. The supplied case brief is the authority for competition requirements. This contract fixes implementation choices where the brief is silent.

## Product and boundaries

CashProof is a local video review service for possible violations of bank cashier procedures. It produces inspectable evidence and supports a human decision. It does not identify faces, infer intent, pronounce guilt, verify accounting entries, or certify that an entire operation complied with law. Its working title does not imply ForteBank endorsement.

Deliver a public web service and a Windows desktop application using the SAME React application and SAME Python inference service. The RTX 4060 8 GB machine is the inference host. The GTX 1650 4 GB machine is the frontend build machine and a connected desktop client. Offline inference must be demonstrated on the qualified 8 GB host; do not claim the weaker computer runs the same model at the same speed.

No supplied footage, frames, crops, embeddings that expose content, transcripts, captions, event descriptions, or screenshots of real cases may be sent to cloud AI, including the coding agent. Generate code with Codex; run models and inspect real cases locally. Coding agents may receive aggregate evaluation and technical error metadata. Use synthetic fixtures for cloud-visible UI review. No face recognition, face embeddings, identification, audio analysis, cloud inference, telemetry containing case data, or runtime model downloads.

## Repository and ownership

Use one repository and a common baseline commit. Keep `forte_handoff/` as read-only planning material. Copy `forte_handoff/contracts/` to `packages/contracts/` ONCE before branches diverge. Both developers start from that commit. Do not create two independent apps and attempt to combine their conventions later.

```text
cashproof/
  forte_handoff/                 planning material, unchanged during parallel work
  packages/contracts/           A owns after initial shared freeze; B consumes
    openapi.json                HTTP authority, version 1.0.0
    fixtures/*.json             synthetic API states only
  services/backend/             A owns all Python, dependencies and lock
    pyproject.toml
    uv.lock
    src/cashproof/
      bootstrap.py              process startup and static frontend serving
      api/                      jury endpoints and richer UI endpoints
      jobs/                     persistent SQLite queue and lifecycle
      media/                    decoding, timestamp map, previews, JPEGs
      inference/                local model adapters and bounded scheduler
      rules/                    predicates, versioned registry, evidence gates
      storage/                  per-job files and retention
    tests/                      A owns meaningful backend and contract tests
  apps/web/                     B owns React, TypeScript and UI tests
    src/api/                    generated types plus HTTP client
    src/features/               upload, review, rules, health, export
    src/components/
    src/styles/
    src/mocks/                  fixtures enabled only in explicit demo/dev mode
  apps/desktop/                 B owns Electron main, preload and packaging
  package.json                  B owns JavaScript workspaces and commands
  pnpm-workspace.yaml            B owns
  pnpm-lock.yaml                 B owns, single writer
  tsconfig.base.json             B owns
  infra/                        A owns deployment and offline setup scripts
  tools/                        A owns evaluation, contract checks, bundle builder
  docs/backend/                 A owns runbook, model card, legal sources, errors
  docs/frontend/                B owns UX, desktop instructions, pitch script
  docs/integration/              A owns shared release evidence and handoff log
  assets/rules/                 A owns checked public legal source snapshots
  models/                      ignored, downloaded before offline operation
  private-data/                ignored, local development only
  runtime-data/                ignored, jobs and case files
  releases/                    ignored, build output
  .gitignore                   A owns; covers all above private/output folders
  .env.example                 A owns; names only, no real credentials
  README.md                    A owns root launch and submission instructions
```

B owns all JavaScript dependency changes; A owns all Python dependency changes. A may request a UI script change in `docs/backend/requests-for-b.md`; B may request server/contract changes in `docs/frontend/requests-for-a.md`. Neither overwrites the other's area. Agree on an additive contract revision before changing fields. Put generated TypeScript under `apps/web/src/api/generated/`; it is B-owned and generated from the checked contract, never manually patched.

Branches: `codex/backend` and `codex/frontend`. Merge small vertical slices at hours 2, 5, 9, 14 and 18. A is the release integrator. B merges/rebases the common integrated branch before continuing after each checkpoint. Never force-push shared work or resolve an unfamiliar conflict by choosing one whole side. File ownership reduces textual conflicts; contract and integration checks establish compatibility.

## Technology decisions

Frontend: React, TypeScript, Vite, Tailwind CSS, Lucide, and a small accessible component set. Bundle fonts/icons locally. Use one package manager, pnpm. Avoid a second UI framework or a server-rendered frontend that complicates desktop packaging.

B supplies stable root commands: `pnpm dev:web`, `pnpm build:web`, `pnpm dev:desktop`, `pnpm build:desktop`, and `pnpm check:ui`. `build:web` emits `apps/web/dist`; `build:desktop` consumes that directory plus A's `releases/backend` bundle. A's service entry point is `python -m cashproof.bootstrap`. Pin exact commands and dependency versions in the appropriate owner documentation after they run successfully.

Backend: Python 3.11 or 3.12, FastAPI, Pydantic, SQLite WAL, FFmpeg/ffprobe, local model adapter. Choose the exact mutually compatible package versions during the initial smoke run and lock them. Do not use floating `latest` dependencies in the release. A single durable queue and a single GPU worker are enough. Persist transitions and final results atomically. Heavy inference must not block the HTTP process.

Model starting point on RTX 4060: `Qwen/Qwen3-VL-2B-Instruct`, from its official repository with a pinned revision. Start with supported PyTorch/Transformers, bounded pixels/frames/context, and one job. Benchmark actual memory and latency before choosing precision. Quantization or a larger model is optional only if it produces a measurable validation benefit within the same latency budget. Do not assume a 2B model's weights alone describe peak memory. Avoid spending the hackathon porting vLLM or compiling FlashAttention on Windows. A smaller model is a fallback to evaluate, not a guarantee of acceptable accuracy.

## Jury API

The machine-readable authority is `contracts/openapi.json`. These endpoints strictly require `X-API-Key`; missing/wrong key returns 401. No login screen, cookie, browser challenge or CSRF token may be required by the jury client.

`POST /api/v1/analyze`, multipart form field `file`, accepts MOV and returns HTTP 202 with only `{ "job_id": "opaque-id" }`. Stream to a safe generated filename. Limit to 128 MiB initially, comfortably above supplied files, and validate the actual container/codec. Reject unsafe/unsupported input using a documented HTTP error; do not trust extension or user filename. Do not impose 145 seconds as a hard competition limit because it describes the provided set rather than an explicit API restriction.

`GET /api/v1/jobs/{job_id}` returns one of:

```json
{"job_id":"opaque-id","status":"processing"}
```

```json
{"job_id":"opaque-id","status":"done","verdict":"no_violation","violations":[]}
```

```json
{"job_id":"opaque-id","status":"done","verdict":"violation","violations":[{"type":"Human-readable event category","timecode_sec":12.4,"description":"Observed action and cautious reason for review","evidence_frames":[{"timestamp_sec":12.4,"image_base64":"RAW_BASE64_JPEG_WITHOUT_DATA_URI_PREFIX"}]}]}
```

```json
{"job_id":"opaque-id","status":"failed","error":{"code":"DECODE_FAILED","message":"The video could not be decoded."}}
```

There are exactly TWO verdict values. `insufficient_data`, `unknown` and `needs_review` are not verdicts. `failed` describes an actual technical failure, never a deliberate way to avoid difficult classification. A readable but partially occluded video may complete; communicate coverage limitations in the UI detail. An unreadable or incomplete analysis must not be represented as a successful negative result.

When done, `violation` requires at least one supported event and `no_violation` requires an empty event list. Each event has 1–3 actual JPEG frames, original-video timestamps as numbers, a concrete category, and a concise explanation. Sort events by timestamp. Merge only detections of the same event, not different simultaneous violation types. Never use stringified numbers, NaN, a URL instead of base64, or annotated/generated images as original evidence. Keep the jury response minimal; legal references and diagnostic detail live in the UI projection below. The response's `description` may include a short verified rule citation without adding schema fields.

## UI API and identity

All `/api/ui/*` endpoints also use `X-API-Key`. The operator enters an access key once; hold it in memory, never a bundled universal secret or URL parameter. Browser refresh may require re-entry. Desktop receives a random per-launch local key through a narrow preload bridge; it is not compiled into the renderer. API keys can grant jury or operator scopes; jury keys must not read unrelated cases or delete them.

Required UI endpoints are fixed in OpenAPI:

| Endpoint | Purpose |
| --- | --- |
| GET `/api/ui/cases` | Local case list with safe metadata |
| GET `/api/ui/cases/{job_id}` | Progress and enriched result with stable event IDs |
| GET `/api/ui/cases/{job_id}/media` | Authenticated MP4 preview; renderer fetches Blob |
| PUT `/api/ui/cases/{job_id}/reviews/{event_id}` | Separate human review decision and note |
| GET `/api/ui/cases/{job_id}/bundle` | ZIP with report, evidence, references and hash manifest |
| DELETE `/api/ui/cases/{job_id}` | Operator deletion of local case artifacts |
| GET `/api/ui/rules` | Versioned rule registry and source links |
| GET `/health/live` | Process liveness, no auth, no sensitive details |
| GET `/health/ready` | Actual model/worker readiness; 503 until ready |

Use the jury POST for upload, then poll UI case detail every 1–2 seconds with backoff and cancellation on navigation. Show uploaded bytes separately from processing stages. Expose real stage names (`queued`, `decoding`, `screening`, `verifying`, `packaging`, `complete`, `failed`); percentages are nullable when the worker cannot measure them. Never invent a smoothly advancing progress bar or a precise ETA without measurements.

`event_id` is persisted once. UI events align with jury events by stable index recorded in the result, not fuzzy matching on localized text. `model_result` is immutable. Human decisions are `unreviewed`, `confirmed`, `dismissed` or `uncertain`; these are human workflow states, not API verdicts. Store the original automated result separately.

Case detail includes `rules`, an immutable snapshot of the rules referenced by that case, and `review_cues`, a separate array for unsupported observations. The event source drawer uses the case snapshot, not the latest global registry. Rule-library browsing uses `/api/ui/rules`. Empty `review_cues` is valid; cues never count as jury violations or change the verdict. A disabled rule must never produce a real violation. The synthetic fixtures deliberately use a disabled synthetic rule and can run only in visibly labeled development mode.

All times are seconds on the original decoded presentation timeline with the first displayed frame at 0. Capture actual presentation timestamps, honor MOV edit lists/rotation, and maintain an explicit source-to-preview mapping. Most supplied files have variable sample timing. Do not calculate time as frame index divided by 30. Browser preview remux/transcode must not introduce an untracked offset. Draw optional overlays in the UI, preserve the raw image separately, and never alter evidence pixels in the jury response.

For small supplied files the browser may fetch an authenticated MP4 Blob and revoke its object URL on cleanup. Backend creates a compatible MP4 preview locally; preserve aspect ratio and avoid upscaling inference input without a reason. `media` returns 409 if the preview is not ready. Preview generation cannot delay the jury verdict past its deadline.

## Deployment and desktop process contract

Web production serves static `apps/web/dist/` and `/api` from the same HTTPS origin. Vite development proxies `/api` and `/health` to `127.0.0.1:8000`. No frontend assumptions about separate production ports or hardcoded localhost URLs.

Desktop default is an offline application on the qualified GPU computer. B packages Electron plus web build; A supplies a tested portable backend bundle at `releases/backend/`:

```text
backend/
  python/python.exe
  app/cashproof/...
  models/...
  bin/ffmpeg.exe
  bin/ffprobe.exe
  manifest.json
```

The bundle includes Python packages at a documented location and the runtime configuration needed to import them. A provides `backend/launch.json` containing `executable` (relative), `args_prefix`, `cwd` (relative), and environment additions. B reads this validated manifest; it does not guess the Python layout. Example command after the prefix:

Validate the manifest against `packages/contracts/desktop-launch.schema.json`. It also includes `contract_version: "1.0.0"`. Resolve executable and cwd against the backend bundle and reject paths escaping it. Environment additions must contain no baked-in API key. Relative model paths are resolved from the declared cwd. B adds the runtime key and offline/server configuration explicitly.

```text
-m cashproof.bootstrap --host 127.0.0.1 --port 0 --data-dir <userData>/cases --frontend-dir <resources>/web
```

A handles `port 0` and prints ONE JSON readiness line to stdout only after HTTP is bound: `{"event":"http_ready","port":49152}`. Model readiness remains separately polled at `/health/ready`. Other logs go to stderr, with no video descriptions or keys. Electron passes `CASHPROOF_API_KEY` randomly generated per launch and `CASHPROOF_MODE=offline`; the backend binds loopback. B launches without `shell:true`, handles Unicode/space-containing paths, hides the console, uses startup timeouts, and terminates only its own child process tree on exit. The persistent model worker may take longer to warm than the HTTP server; show truthful startup status.

Electron uses `contextIsolation:true`, `sandbox:true`, `nodeIntegration:false`; expose only a typed configuration bridge. Deny arbitrary navigation, uncontrolled external URLs, and unrestricted IPC. The packaged UI is served by the local backend, so web and desktop keep the same API origin. A connected mode can point to the team's HTTPS GPU host, visibly labeled as remote. Do not label that mode offline. A portable Windows release is sufficient; a signed installer and macOS/Linux builds are outside the 23-hour plan.

Public jury deployment should reach the team-controlled inference host over HTTPS. Resolve inbound reachability in hour 1. Do not silently upload test data to an AI service or a third-party storage/relay. If direct inbound access is impossible, obtain the organizer's approval of the intended relay/hosting arrangement before using private footage. Model inference must remain within the deployed service. Check from a genuinely external network, not only localhost. Keep the PC powered, awake, plugged in, and the API stable during judging.

## Latency and durable processing

The competition limit is 300 seconds per video. Internal targets are goals until benchmarked: admission/upload receipt under 5 seconds after transfer, end-to-end p95 under 240 seconds, watchdog at 270 seconds to leave response headroom. Include queue time and decoding in measurements. A queued `processing` result does not stop the jury timer.

Start with one GPU job. Use a bounded queue with an explicit admission response and `Retry-After` when saturated. Clarify expected jury concurrency early. Five simultaneous jobs each taking 100 seconds cannot all meet 300 seconds in a serial queue; measure this instead of claiming capacity from single-video latency. Batch frame encoding or add a genuinely available second worker only after profiling. Do not return a fabricated negative result on timeout or OOM.

SQLite records job ID, state, stage, model/rule versions, content hash and timestamps. Files use generated job directories. On worker crash, mark or resume interrupted work deterministically. Atomic result publication prevents a partially written `done` response. Keep model weights out of Git and pin hash/revision/license. Queue logs must not echo model captions into the coding agent's transcript.

## Legal and inference gates

Rules contain stable ID, Russian display name, official title/URL, paragraph, reviewed revision/effective date, applicability, visible predicates, required context, exclusions and a cautious explanation template. A disabled/unchecked source cannot justify an alert. A model selects existing rule IDs; it may not invent statutes or clause numbers. Cache verified rule text locally before offline operation.

Separate observation from inference and uncertainty. Treat low resolution and occlusion as limits, not proof an action never happened. For omitted steps, require the relevant complete visible sequence; choose the first instant at which the expected step should already have occurred. A generic anomaly score alone cannot establish a legal violation. A novel visual event is checked against the same verified predicates; unsupported anomalies stay in an explicitly separate review cue and do not silently become jury violations.

Never use file names, sequence numbers, label tables, hashes, duration thresholds or camera identity as predictors. Hashes are for deduplication/provenance only. Development data must not be mounted into the production prediction path. Evaluate under renamed files as a leakage check.

## Merge acceptance

A validates the exact jury schema, binary verdict invariants, JPEG decoding, authentication, timestamp bounds, local-only inference, queue/restart behavior and real media processing. B validates generated types, complete UI states, keyboard navigation, portrait video layout, mock/production separation and desktop startup/shutdown. Together validate upload to real result in web and desktop, then a fresh machine/bundle launch with internet disabled after downloads. Use synthetic media for coding-agent-visible tests; local humans review private video quality.

Do not call the release complete if only mocks work, a notebook must be launched by hand, desktop is only a browser shortcut, a fallback returns constant results, or the public URL has not been exercised externally. No architecture document can guarantee a conflict-free or correct merge; these ownership rules and executed checks are the evidence required to claim one.
