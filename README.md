# CashProof · ForteBank Datathon

Local video review for possible cashier-procedure violations, with source-linked evidence and a separate human decision.

**Status:** backend and B's React/Electron frontend are integrated on contract 1.0.0. The local same-origin GPU service is running at `http://127.0.0.1:8000`; a new 28.7 MB development MOV completed through the separate jury key in 22.05 seconds. There are 23 passing backend tests, 43 UI/security tests, three browser/API synthetic scenarios and two production browser checks. Detection quality remains inadequate: the baseline development run missed all 15 positives (27 completed, one technical failure out of 28). The full packaged Windows EXE also processed a new real MOV in 33.63 seconds, with ZIP export/reload/shutdown verified. A checksummed private backend archive is ready. The public UI/API at https://cashproof-web.vercel.app now reaches the local GPU through a human-authorized temporary Cloudflare tunnel: a real 28.7 MB upload completed in 60.625 seconds. Independent cross-machine access, full disconnected desktop execution and useful detection quality remain open. See [A's handoff to B](docs/integration/A_TO_B_STATUS.md) and [verification](docs/integration/verification.md).

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

`127.0.0.1` is usable only on this computer. B can now use https://cashproof-web.vercel.app with the existing keys delivered privately; see the [connected deployment handoff](docs/integration/VERCEL_WEB_HANDOFF.md). Keep the team server and temporary tunnel running; do not run heavy model experiments alongside them. Desktop uses `--port 0`, loopback and a fresh per-launch key. The single stdout `http_ready` line reports the bound port; model readiness is a separate health check. Full offline packaging uses `pnpm build:desktop` after placing the verified private bundle at `releases/backend`. See the [runbook](docs/backend/runbook.md).

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

Read [AGENTS.md](AGENTS.md), the [shared contract](forte_handoff/SHARED_CONTRACT.md) and the relevant master prompt before editing. Keep `forte_handoff` unchanged. No B-owned files were edited in the backend workstream.

The [architecture](docs/backend/architecture.md), [integration evidence](docs/integration/verification.md), [desktop launch schema](packages/contracts/desktop-launch.schema.json) and `tools/build_bundle.py` cover the release handoff. The bundle builder refuses missing prerequisites. A source folder, mock result or assembled bundle alone is not offline proof.

The current public route is Vercel CDN → Cloudflare Tunnel → local inference. The human approved real-video transport after disclosure; organizer approval is not recorded. New synthetic and real uploads passed through the public origin from this host. An independent client/network and continuous jury-window availability remain unverified. The temporary upstream changes on restart; update both project routing rules before use. This route is an integration service, not a competition-readiness claim.

CashProof is a working title and does not imply ForteBank endorsement.
