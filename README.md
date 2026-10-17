# CashProof · ForteBank Datathon

Local video review for possible cashier-procedure violations, with source-linked evidence and a separate human decision.

**Status at common audit, 18 October 2026:** backend 0.3.2 and the React/Electron frontend are integrated on contract 1.0.0. The new private portable bundle and full Windows package passed integrity and real-model execution checks. The local API is restored from that bundle with original credentials. Public API routing still awaits publication of the prepared replacement rewrites; the updated static site is published and all 11 public files match the checked local build. Full development evaluation completed: production recall 0/15; Qwen3.5-4B is rejected with 12/28 technical failures and no successful positive detections. Useful recognition, independent access, disconnected desktop qualification and redistribution review remain open. See the [whole-project status](docs/integration/PROJECT_STATUS.md), [acceptance matrix](docs/frontend/INTEGRATION_CHECKLIST.md) and [executed evidence](docs/integration/verification.md).

## Backend setup

Use Windows, Python 3.12 and the qualified RTX 4060 8 GB host. Provision dependencies and weights while online, then run inference locally. No footage, extracted frames or descriptions may be sent to cloud AI.

```powershell
./infra/setup.ps1 -Python 3.12
$env:HF_HUB_DISABLE_XET='1'
.venv/Scripts/python.exe tools/provision_model.py
$env:CASHPROOF_API_KEY = .venv/Scripts/python.exe -c 'import secrets; print(secrets.token_urlsafe(32))'
$env:CASHPROOF_MODE='offline'
.venv/Scripts/python.exe -m cashproof.bootstrap --host 127.0.0.1 --port 8000
```

The setup script requires `uv` on PATH (or `-Uv <path-to-uv.exe>`) and uses the pinned `services/backend/uv.lock` and CUDA 12.8 PyTorch index. Model provisioning pins the official Qwen checkpoint revision and verifies all asset hashes. A missing model keeps `/health/ready` at 503; it never starts a download or returns a fixture prediction.

Run checks:

```powershell
.venv/Scripts/python.exe -m pytest services/backend/tests -q
```

## Common web and Windows build

Use Node >=24.13 (qualified locally: 24.19.0) and pnpm 11.25.0:

```powershell
pnpm install --frozen-lockfile
pnpm check:ui
pnpm build:web
pnpm build:desktop:connected
```

Serve the production UI with `--frontend-dir apps/web/dist`; the same backend origin handles `/`, `/api/*` and `/health/*`. Use `CASHPROOF_MODE=server` and distinct random operator/jury keys. The local team launcher preserves keys in ignored runtime data and never prints them:

```powershell
.venv/Scripts/python.exe tools/start_team_server.py --ffmpeg <prepared-ffmpeg.exe>
```

This workstation actually uses the prepared Python environment at `../../work/.venv/Scripts/python.exe` relative to the repository. Credentials stay at `runtime-data/team-server/credentials.json`; enter the operator value locally in the UI and never paste it into an agent conversation. Do not regenerate keys for an existing case store.

`127.0.0.1` is usable only on this computer. The public site https://cashproof-web.vercel.app still requires replacement API routing before B can use the restored service; see the [connected deployment handoff](docs/integration/VERCEL_WEB_HANDOFF.md). Keep the team server and temporary tunnel running; do not run heavy model experiments alongside them. Desktop uses `--port 0`, loopback and a fresh per-launch key. The single stdout `http_ready` line reports the bound port; model readiness is a separate health check. Full offline packaging uses `pnpm build:desktop` after placing the verified private bundle at `releases/backend`. See the [runbook](docs/backend/runbook.md).

## API and results

The unchanged [OpenAPI 1.0.0](packages/contracts/openapi.json) defines all fields. `POST /api/v1/analyze` accepts multipart `file`, requires `X-API-Key`, and returns HTTP 202 with only an opaque `job_id`. `GET /api/v1/jobs/{job_id}` returns `processing`, `done` or a technical `failed`. Completed verdicts are exactly `violation` and `no_violation`.

The Russian UI result wording is `Нарушение не обнаружено` / `Обнаружены признаки возможных нарушений`. A negative means no visible signs within enabled scope; it is not a compliance certificate. Each event has actual source PTS and 1–3 unannotated JPEGs. Human review never changes the original automated result.

The backend includes a SQLite WAL queue, bounded admission, a supervised local model worker, full-video screening and temporal verification, validated source/preview timestamps, immutable case rule snapshots, review persistence and ZIP export. It initially admits one pending/active job; 429 includes `Retry-After`. Five short synthetic jobs do not establish capacity for five long videos.

## Rules, privacy and evaluation

Only Resolution No. 231 §22 is enabled as an experimental detector. Six other researched candidates are disabled pending local validation. See [legal sources and scope](docs/backend/legal-sources.md). The service does not identify people, infer intent or permissions, verify ledger entries, analyze audio or pronounce guilt.

`private-data`, `runtime-data`, `models`, keys and releases are ignored by Git. Dataset filenames, hashes and labels are used for integrity, grouping and evaluation, never prediction. The returned manifest marks grouping reviewed and has 28 development and 12 validation unique videos; structural checks do not independently establish scene/view independence. Both times on the duplicate positive video are preserved. Only aggregate evaluation output belongs in coding-agent conversations.

## Team and release

Start from shared baseline `322afabd1daebc15d25846ac5fd4f62cd1c8c3d0`.

| Owner | Scope | Branch |
| --- | --- | --- |
| A | Python, local model, media, rules, evaluation, deployment, release integration | `codex/backend` |
| B | React/TypeScript web, Electron desktop, JavaScript dependencies | `codex/frontend` |

Read [AGENTS.md](AGENTS.md), the [shared contract](forte_handoff/SHARED_CONTRACT.md) and the relevant master prompt before editing. Keep `forte_handoff` unchanged. The owner subsequently authorized A to finish missing frontend/desktop work during the common audit; those changes preserve the shared contracts and existing B implementation.

The [architecture](docs/backend/architecture.md), [integration evidence](docs/integration/verification.md), [desktop launch schema](packages/contracts/desktop-launch.schema.json) and `tools/build_bundle.py` cover the release handoff. The bundle builder refuses missing prerequisites. A source folder, mock result or assembled bundle alone is not offline proof.

The current public route is Vercel CDN → Cloudflare Tunnel → local inference. The human approved real-video transport after disclosure; organizer approval is not recorded. Historical synthetic and real uploads passed through the earlier public route from this host; that upstream is now dead and replacement rewrites are not yet published. An independent client/network and continuous jury-window availability remain unverified. The temporary upstream changes on restart; update both project routing rules before use. This route is an integration service, not a competition-readiness claim.

CashProof is a working title and does not imply ForteBank endorsement.

## Published static build, 18 October 2026

The existing production alias now serves the Git build from a1fa9d2a44a3c5c5953302460a8d75d6da09953e, deployment82s7f2A3sLFQg8eXEugSp9UG4zaR (Ready,18s). All11 public files (736,036bytes) were fetched anonymously and matched the corrected Windows build byte-for-byte; security headers and absence of actual credential values were checked. Public login rendered without accessing private cases. Explicit LF attributes preserve identical static/license bytes on Windows and Linux. The earlier prepared Drop directory is retained as historical and is not the final public fingerprint.

The owner prioritizes an accurate single service. API/health are two technical paths of that one service, not competing models. The latest response did not approve routing Publish; both rewrites remain Draft while recognition quality is unresolved. The local portable API/tunnel are ready, but current public API readiness is false. No claim of universally correct diagnosis is made.
