# A to B: integration handoff, 17 October 2026

Backend 0.3.1 and frontend e03e5a9 are integrated on unchanged contract 1.0.0. Use the latest codex/integration (draft PR #3). The packaged runtime source is 4a69e19d99b1fbf0e35b6991b0a68a88bd5f0d8d; subsequent commits add verification tools and receipts. Main remains unchanged pending explicit approval after automatic review rejected the main push. This is an engineering integration candidate; detection quality is inadequate for submission.

| Requested item | Actual state |
| --- | --- |
| UI/API | http://127.0.0.1:8000 on A's workstation only |
| Public HTTPS / separate-PC access | Not provisioned or verified; team host/inbound route unavailable |
| Health | ready=true, mode=server, contract_version=1.0.0; current startup 25.312 s |
| Credentials | Distinct persistent operator/jury keys saved locally in ignored runtime-data/team-server/credentials.json; never published |
| Model | Qwen/Qwen3-VL-2B-Instruct, revision 89644892e4d85e24eaac8bacfd4f463576704203, BF16/SDPA, local files only |
| Registry | 2026-10-17.3; paragraph 22 experimental, six other candidates disabled |
| New real analysis | 28.7 MB development MOV, jury POST/poll, 1 accepted/1 done/0 failed, 22.050 s including upload |
| Web checks | 43 UI/security tests, 3 synthetic API/browser scenarios, 2 production browser checks pass |
| Backend checks | 23 tests pass, including owner-only crash cleanup of worker and descendant |
| Positive / multi-event real cases | Not qualified; existing synthetic scenarios are engineering tests only |
| Development | 28 unique: 27 completed, 1 technical failure; TP=0, TN=12, FP=0, FN=15; recall 0/15, precision undefined |
| Validation | Not opened for selection or evaluation |
| Admission | One active/pending job; saturation 429 + Retry-After; no five-long-video capacity claim |
| Portable bundle | releases/backend: 0.3.1 candidate, 20,528 hashed files plus manifest, 12.29 GB; verified archive 7,323,874,414 bytes; prior 0.2/0.3 rc1 folders must not be shipped |
| New fully disconnected RTX 4060 analysis | Not verified; Python socket guard is not OS/network disconnection |
| Joint 45–60 minute session | Not scheduled; requires B-accessible HTTPS first |

Actual startup from repository root uses ../../work/.venv/Scripts/python.exe tools/start_team_server.py --ffmpeg ../../work/ffmpeg-9.0.2/ffmpeg.exe. The launcher runs cashproof.bootstrap with host 127.0.0.1, port 8000, runtime-data/team-server/cases and apps/web/dist. It preserves the existing keys. Keep the computer and GPU available during an agreed integration window; do not run model experiments concurrently with the service.

B can already build/check the common source and exercise synthetic integration. Separate-PC live integration remains blocked on a permitted HTTPS route. An external-network jury POST/poll, useful recognition quality, a qualified portable package, disconnected desktop run and real-event source/time review remain explicit gates. No frontend-only test satisfies these gates. Follow docs/frontend/INTEGRATION_CHECKLIST.md; do not mark I01–I18 globally PASS from these partial results.

The real browser flow completed upload, model response, export and re-login with zero JavaScript errors. Its external-request guard blocked two requests to http://me.kis.v2.scr.kaspersky-labs.com; no zero-external-request browser pass is claimed. The installed security environment was not modified. The actual live GPU server was then killed by its owner PID only: two immediate child processes before, zero surviving children after two seconds. This is additional real-process cleanup evidence, not a disconnected desktop qualification.

## Completed portable and Windows evidence

The bundled Python/model launched from a path containing spaces and Cyrillic, warmed in 33.390 s, and completed a new synthetic MOV via HTTP in 4.697 s with external Python sockets denied. This is not OS-level disconnection. All 17 bundled Python source files independently match clean source commit 4a69e19d99b1fbf0e35b6991b0a68a88bd5f0d8d; source_dirty=false.

The full packaged `apps/desktop/dist/offline/win-unpacked/CashProof.exe` then completed a new real 28,718,927-byte development MOV using its own Python/model: startup 39.710 s, upload-to-visible-result 33.628 s, health ready=true/mode=offline/contract=1.0.0. ZIP saving, reload restoration and backend shutdown after closing the app passed; zero renderer JavaScript errors and zero external renderer requests were observed. The host network remained connected, so I17 is NOT PASS. Real positive/multi-event semantic review and event review persistence remain unqualified; do not infer those from a completed negative model result.

The first packaged probe had completed inference but timed out waiting for Playwright's generic download event. Repeating once with Electron's actual will-download API and an explicit private destination completed successfully; no B-owned source was changed. The exported ZIP was fully read and CRC checked, with every report/configuration/source entry's SHA-256 verified.

Both connected and full Windows folders were built from the common checkout. Four desktop tests passed in 10.6 s, including connected EXE startup, synthetic Unicode-path lifecycle, sandboxed bridge and incompatible-contract handling. Transfer the entire win-unpacked folder, not just its EXE. This machine's RTX 4060 is the measured host; GTX 1650 4 GB remains unqualified.

Private backend archive: `releases/backend-0.3.1-rc1 проверка.zip`, 7,323,874,414 bytes.
SHA-256: `a95c465b8cf2eacd5818381431ec2b0d055e1c97728813160b916d7396cacc16`.
The adjacent `.zip.sha256` file repeats this checksum. All 20,529 file/manifest records were verified before streaming the ZIP; it was reopened and 24 critical source/rule/launch/model-manifest entries rehashed from compressed contents. Public binary redistribution remains unreviewed, including FFmpeg corresponding-source obligations.

The persistent local team server has been restored with its original keys. No model experiment is running alongside it. External HTTPS and the joint 45–60 minute separate-PC window still require a permitted route. Main publication remains blocked pending explicit approval; use draft PR #3 / codex/integration meanwhile.
