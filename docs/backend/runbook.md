# Local runbook

Python 3.11/3.12 is required; 3.12.14 is qualified in development. System Python 3.13 is outside the supported range. Provision dependencies and CUDA wheels before offline inference. `uv` must be on PATH, or supply `-Uv <absolute-path-to-uv.exe>`; `-Python` also accepts a Python executable path.

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

A local human must review related-take groups, adjust the provisional 28/12 unique-video split and set `related_groups_reviewed=true` before evaluation. For the supplied dataset this review was returned and checked: 28 development unique videos (15 positive/13 negative), 12 validation (6/6), 40 groups, no cross-split duplicates. Exact duplicates must stay together; both positive duplicate times remain separate annotations. Do not expose local review notes to this coding chat. Once the split is locked:

```powershell
.venv/Scripts/python.exe tools/evaluate.py --manifest private-data/evaluation-manifest.json --model-dir models/Qwen3-VL-2B-Instruct --rules assets/rules/registry.json --output private-data/evaluation --split development
```

Repeat with `--split validation --freeze-from private-data/evaluation/DEVELOPMENT_RUN_ID/aggregate.json` only after freezing configuration. The command rejects a changed implementation, registry, model manifest or split. A partial engineering run cannot freeze validation. The same `Pipeline` is used by API workers and evaluation. Full predictions/evidence stay private; only `aggregate.json` is safe for this chat. Report failures separately and include all denominators. Type accuracy and event F1 remain null because the supplied labels do not support them. Reused validation is no longer blind.

For private category review, generate `local-taxonomy-review.html` with `tools/create_taxonomy_page.py`. It includes only positive development examples. Human category notes and video content remain in ignored local files; do not copy them into Git or a coding-agent conversation. Unknown categories do not authorize invented legal citations.

Portable launch uses `launch.json` from the assembled folder, with relative executable/cwd/env values resolved against that folder. Set `CASHPROOF_API_KEY` at runtime; append `-m cashproof.bootstrap --host 127.0.0.1 --port 0 --data-dir <persistent-userData>` to `args_prefix`. No system Python or online package/model provisioning is needed after assembly. Verify file hashes with `tools/verify_bundle.py --bundle <folder>`; add `--archive` to create a checked ZIP and SHA-256 sidecar. Never modify a published folder in place.

`infra/verify-offline.ps1 -Bundle <folder> -Video <local-video> -Output <private-output>` requires an Administrator PowerShell. It creates temporary outbound block rules for the specified bundled Python/pythonw/FFmpeg/ffprobe paths, tests an external connection is blocked, runs the genuine loopback API, and removes only its own rules in `finally`. The current session is not Administrator; this Windows Firewall qualification has not run. The already executed Python socket guard is narrower evidence.

## Prepared test with the host actually disconnected

`infra/verify-disconnected-desktop.ps1 -Node <prepared-node.exe> -CheckOnly` checks the installed packaged EXE, test inputs, physical links and default routes without changing any setting or starting inference. On this host preflight found one active physical link and one connected default route, so an offline pass cannot be claimed.

To run later, stop other GPU inference, manually disconnect Wi-Fi/Ethernet/VPN, then invoke the same script without `-CheckOnly` from a local PowerShell. The agent cannot communicate while this host is disconnected; the prepared local script performs the new real MOV analysis itself, saves the ZIP and a receipt, and closes only its own packaged app/backend. It never disables adapters, changes firewall rules or needs administrative privileges. It refuses to start while a physical link/default route remains, requires a native external TCP probe to fail, and samples link/route state while the local EXE test runs. If networking returns early, no disconnected-runtime PASS is recorded. Receipts stay in ignored private-data/disconnected-desktop.

This wrapper is prepared and preflighted, not executed with the host disconnected. A successful receipt would qualify the measured disconnected runtime flow; it would still not make all I17 criteria PASS because positive/multiple-event semantic, source-time and real-event review checks remain separate and currently unqualified. The actual Windows app itself needs neither Node nor this test wrapper; those are prepared verification dependencies only.
