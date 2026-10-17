# A to B: integration handoff, 17 October 2026

Backend 0.3.1 and frontend e03e5a9 are integrated on unchanged contract 1.0.0. Use the published common main revision, not an older backend-only checkout. This is an engineering integration candidate; detection quality is inadequate for submission.

| Requested item | Actual state |
| --- | --- |
| UI/API | http://127.0.0.1:8000 on A's workstation only |
| Public HTTPS / separate-PC access | Not provisioned or verified; team host/inbound route unavailable |
| Health | ready=true, mode=server, contract_version=1.0.0; startup 24.781 s |
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
| Portable bundle | Assembly and runtime verification in progress; prior rc1 folders must not be shipped |
| New fully disconnected RTX 4060 analysis | Not verified; Python socket guard is not OS/network disconnection |
| Joint 45–60 minute session | Not scheduled; requires B-accessible HTTPS first |

Actual startup from repository root uses ../../work/.venv/Scripts/python.exe tools/start_team_server.py --ffmpeg ../../work/ffmpeg-9.0.2/ffmpeg.exe. The launcher runs cashproof.bootstrap with host 127.0.0.1, port 8000, runtime-data/team-server/cases and apps/web/dist. It preserves the existing keys. Keep the computer and GPU available during an agreed integration window; do not run model experiments concurrently with the service.

B can already build/check the common source and exercise synthetic integration. Separate-PC live integration remains blocked on a permitted HTTPS route. An external-network jury POST/poll, useful recognition quality, a qualified portable package, disconnected desktop run and real-event source/time review remain explicit gates. No frontend-only test satisfies these gates. Follow docs/frontend/INTEGRATION_CHECKLIST.md; do not mark I01–I18 globally PASS from these partial results.
