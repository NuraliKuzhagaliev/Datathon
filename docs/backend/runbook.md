# Local runbook

Python 3.11/3.12 is required. The current development interpreter is Python 3.12.14; the system Python 3.13 is outside the supported range. Dependencies and CUDA wheels must finish provisioning before local inference can start.

From the repository root in PowerShell:

```powershell
./infra/setup.ps1 -Python 3.12
$env:HF_HUB_DISABLE_XET='1'
.venv/Scripts/python.exe tools/provision_model.py
$env:CASHPROOF_API_KEY = .venv/Scripts/python.exe -c 'import secrets; print(secrets.token_urlsafe(32))'
$env:CASHPROOF_MODE='offline'
.venv/Scripts/python.exe -m cashproof.bootstrap --host 127.0.0.1 --port 8000
```

Use the pinned CUDA 12.8 PyTorch index configured in `pyproject.toml` with uv. Never install a CPU wheel and assume GPU readiness. Store keys in the process environment; deliver the jury key privately, never in Git, a URL or a command transcript. A separate `CASHPROOF_JURY_KEY` grants upload/poll access only. The operator key has all UI capabilities.

Startup prints one JSON line after binding, for example `{"event":"http_ready","port":8000}`. `/health/live` is HTTP liveness; `/health/ready` remains 503 until the actual local model and enabled registry are ready. Missing/bad weights do not trigger a download or a constant fallback. Readiness failure is intentional until provisioning succeeds.

The server uses one persistent GPU subprocess. SQLite WAL stores jobs, transitions, immutable results and separate reviews. One server owns a data directory via a process lock. On restart unfinished jobs fail with `WORKER_RESTARTED`; they are never silently reported clean. The supervisor kills its worker tree at the configured watchdog (maximum 270 seconds including queue wait). Upload admission is bounded, initially one active/pending job; larger values require measured concurrency evidence. An unreadable file is rejected at ingest or fails during full decoding. OOM, deadlines, invalid model JSON after one repair and exhausted analysis budgets remain technical failures.

All MOVs are decoded with actual PTS starting at the first displayed frame. FFmpeg applies rotation and extracts unannotated JPEGs; sampled frames are checked against the decoder timeline. Preview transcode runs after atomic verdict publication, in a separate bounded artifact worker. Its frame-by-frame PTS map must match within 2 milliseconds before `media_ready=true`.

## Jury example

```powershell
curl.exe -X POST https://YOUR-TEAM-HOST/api/v1/analyze -H "X-API-Key: $env:CASHPROOF_JURY_KEY" -F 'file=@synthetic.mov'
curl.exe https://YOUR-TEAM-HOST/api/v1/jobs/RETURNED_JOB_ID -H "X-API-Key: $env:CASHPROOF_JURY_KEY"
```

No public hostname is provisioned by this source checkout. External HTTPS, organizer hosting approval if a relay handles footage, external-network POST/poll and uptime remain deployment gates. Do not upload competition video to an unapproved relay, external AI or a public issue.

## Private evaluation

```powershell
.venv/Scripts/python.exe tools/prepare_dataset.py --dataset private-data/dataset --output private-data/evaluation-manifest.json
```

A local human must review related-take groups, adjust the provisional 28/12 unique-video split and set `related_groups_reviewed=true` before evaluation. Exact duplicates must stay together; both positive duplicate times remain separate annotations. Do not expose local review notes to this coding chat. Once the split is locked:

```powershell
.venv/Scripts/python.exe tools/evaluate.py --manifest private-data/evaluation-manifest.json --model-dir models/Qwen3-VL-2B-Instruct --rules assets/rules/registry.json --output private-data/evaluation --split development
```

Repeat with `--split validation` only after freezing configuration. The same `Pipeline` is used by API workers and evaluation. Full predictions/evidence stay private; only `aggregate.json` is safe for this chat. Report failures separately and include all denominators. Type accuracy and event F1 remain null because the supplied labels do not support them. Reused validation is no longer blind.
