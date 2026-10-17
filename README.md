# CashProof · ForteBank Datathon

Local video review for possible cashier-procedure violations, with source-linked evidence and a separate human decision.

**Status:** real local GPU upload-to-result works; the longest supplied video completed in 173.01 seconds. Nineteen backend tests pass. Five queued four-second synthetic uploads completed in 4.36–10.94 seconds. Model accuracy, portable runtime qualification, web/desktop integration and public HTTPS remain gates in [verification](docs/integration/verification.md). This checkout is not a completed competition submission.

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

For web integration, supply B's build directory with `--frontend-dir apps/web/dist`. For desktop, use `--port 0`, loopback and a fresh per-launch key. The single stdout `http_ready` line reports the bound port; model readiness is a separate health check. See the [runbook](docs/backend/runbook.md) and [requests for B](docs/backend/requests-for-b.md).

## API and results

The unchanged [OpenAPI 1.0.0](packages/contracts/openapi.json) defines all fields. `POST /api/v1/analyze` accepts multipart `file`, requires `X-API-Key`, and returns HTTP 202 with only an opaque `job_id`. `GET /api/v1/jobs/{job_id}` returns `processing`, `done` or a technical `failed`. Completed verdicts are exactly `violation` and `no_violation`.

The Russian UI result wording is `Нарушение не обнаружено` / `Обнаружены признаки возможных нарушений`. A negative means no visible signs within enabled scope; it is not a compliance certificate. Each event has actual source PTS and 1–3 unannotated JPEGs. Human review never changes the original automated result.

The backend includes a SQLite WAL queue, bounded admission, a supervised local model worker, full-video screening and temporal verification, validated source/preview timestamps, immutable case rule snapshots, review persistence and ZIP export. It initially admits one pending/active job; 429 includes `Retry-After`. Five short synthetic jobs do not establish capacity for five long videos.

## Rules, privacy and evaluation

Only Resolution No. 231 §22 is enabled as an experimental detector. Five other researched candidates are disabled pending local validation. See [legal sources and scope](docs/backend/legal-sources.md). The service does not identify people, infer intent or permissions, verify ledger entries, analyze audio or pronounce guilt.

`private-data`, `runtime-data`, `models`, keys and releases are ignored by Git. Dataset filenames, hashes and labels are used for integrity, grouping and evaluation, never prediction. The local reviewer returned a reviewed split of 28 development and 12 validation unique videos. Both times on the duplicate positive video are preserved. Only aggregate evaluation output belongs in coding-agent conversations.

## Team and release

Start from shared baseline `322afabd1daebc15d25846ac5fd4f62cd1c8c3d0`.

| Owner | Scope | Branch |
| --- | --- | --- |
| A | Python, local model, media, rules, evaluation, deployment, release integration | `codex/backend` |
| B | React/TypeScript web, Electron desktop, JavaScript dependencies | `codex/frontend` |

Read [AGENTS.md](AGENTS.md), the [shared contract](forte_handoff/SHARED_CONTRACT.md) and the relevant master prompt before editing. Keep `forte_handoff` unchanged. No B-owned files were edited in the backend workstream.

The [architecture](docs/backend/architecture.md), [integration evidence](docs/integration/verification.md), [desktop launch schema](packages/contracts/desktop-launch.schema.json) and `tools/build_bundle.py` cover the release handoff. The bundle builder refuses missing prerequisites. A source folder, mock result or assembled bundle alone is not offline proof.

Public HTTPS requires a team-controlled host and an external-network API exercise. No hostname or inbound route has been provisioned. Any relay handling private footage requires organizer clarification before use.

CashProof is a working title and does not imply ForteBank endorsement.
