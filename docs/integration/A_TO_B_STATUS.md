# A to B: current integration handoff

Updated 18 October 2026. This current snapshot supersedes historical maintenance and 0.3.1 readiness notes. Use codex/integration / draft PR #3; main remains 322afabd1daebc15d25846ac5fd4f62cd1c8c3d0. Contract 1.0.0 is unchanged. See [common status](PROJECT_STATUS.md).

| Item | Current evidence and limit |
| --- | --- |
| Runtime | Backend 0.3.2; all 17 bundled Python application sources match clean a034fac203af202b16616b3a0b23d3bb3e0226d7 |
| Local API | Restored from checked releases/backend portable runtime; localhost:8000, ready/server/1.0.0, startup 38.079 s |
| Keys/store | Original distinct operator/jury values and cases preserved in ignored runtime-data; enter keys locally, never in agent chat |
| Model | Qwen3-VL-2B-Instruct pinned 89644892e4d85e24eaac8bacfd4f463576704203; BF16/SDPA, local files only |
| Rules | Registry 2026-10-17.3, experimental paragraph 22 only; other candidates disabled |
| Public site | cashproof-web.vercel.app still serves earlier static build; current public API is not ready |
| Public routing | Old upstream dead. Two API/health replacement rewrites to range-journalism-louisiana-gym.trycloudflare.com are Draft, not published |
| New web build | Prepared and scanned; 11 public assets plus config, 737,189 bytes. Existing Vercel project needs Git/CLI update, not a new Drop project |
| Backend checks | Stable 28 passed / 13.14 s; separate experimental suite 13 passed / one optional-environment skip |
| Web/desktop | 38 UI unit, 20 dev browser, 3 synthetic-model real-API browser, 2 production browser; 5 security + 5 integrity tests, 4 shell scenarios, new Connected smoke |
| Full 0.3.2 Windows | New real 28.7 MB MOV, startup 34.636 s, analyze-to-visible 25.882 s; ZIP CRC/hashes, reload and backend shutdown pass |
| Disconnected | Host stayed online. Prepared verify-disconnected-desktop.ps1 does not change networking; actual disconnected run remains open |
| Production development | 28 done/0 failed; TP0/TN13/FP0/FN15, recall 0/15, precision undefined |
| Qwen3.5 candidate | 16 done/12 failed of 28; TP0/TN7/FP0/FN9 among completed; no successful positive detection, not promoted |
| Validation | 12 unused for inference/tuning; no event-type ground truth or established scene/view independence |
| Admission | One active/pending job; 429 + Retry-After; five-long-video capacity and jury window availability unqualified |

The owner authorized A to complete missing B work: offline license notices, contextual connection errors, manifest-complete packaging and repeatable probes are implemented. Frontend acceptance and pitch documents distinguish tested engineering from unqualified real-event semantics.

Current private full package: apps/desktop/dist/offline-032-audit/win-unpacked/CashProof.exe. Connected: apps/desktop/dist/connected-032-audit/win-unpacked/CashProof Connected.exe. Transfer the entire folder. Checked bundle: releases/backend; new archive SHA-256 f840bf51b4facdb915c2de455b3662c371bad3737d79ce3fc70238b229eed4f9, 7,323,884,572 bytes, all 20,532 ZIP entries checked. Old immutable 0.3.1 artifacts are preserved. Public redistribution remains unreviewed.

Local launch from the development repository uses ../../work/.venv/Scripts/python.exe tools/start_team_server.py --bundle releases/backend --ffmpeg releases/backend/bin/ffmpeg.exe. The launcher executes the bundled Python/model and preserves existing credentials. Do not run a second heavy GPU model alongside the service.

The human authorized Vercel/Cloudflare video and X-API-Key transit; organizer acceptance is not recorded. Never show real case lists, frames, descriptions or reports to a cloud agent. Use synthetic cases for agent-visible work. Before jury submission, establish useful recognition, actual public access, independent-client verification, accepted transport, physical-disconnection execution and applicable license obligations. A successful health check is not model accuracy.
