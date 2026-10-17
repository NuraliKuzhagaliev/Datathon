# Backend integration handoff

Use shared baseline `322afabd1daebc15d25846ac5fd4f62cd1c8c3d0` and unchanged contract 1.0.0. Backend changes are on `codex/backend`. No B-owned files were edited.

- Entry point: `python -m cashproof.bootstrap --host 127.0.0.1 --port 0 --data-dir <userData>/cases --frontend-dir <resources>/web`.
- Set a fresh random `CASHPROOF_API_KEY` (at least 24 characters), `CASHPROOF_MODE=offline`. Read only the single `http_ready` JSON line from stdout. This means HTTP is bound; poll `/health/ready` for model readiness.
- `args_prefix` contains interpreter flags only (currently `-s`). Append `-m cashproof.bootstrap` and then the dynamic arguments exactly as in the shared contract.
- Jury upload/poll and every UI endpoint use `X-API-Key`. Operator key can upload and review; a separately configured jury key can upload/poll only its own submissions. UI denial uses 401 per fixed contract.
- A maximum of one pending/active job is admitted initially; saturated upload returns 429 with `Retry-After: 10`. This is a conservative configuration, not a measured throughput claim.
- Generated request IDs use lowercase opaque hex. All source times are numeric seconds; preview is ready only after every displayed frame's PTS mapping passes validation. A missing preview yields 409 and never delays the verdict.
- Reviews remain separate from immutable `model_result`. Use `jury_violation_index` and stable `event_id`, not localized string matching.
- Show the brief's exact result text: `Нарушение не обнаружено` / `Обнаружены признаки возможных нарушений`. A negative means no signs within enabled scope, not certification.
- Rules currently enable only §22 as an experimental detector. Other researched candidates are explicitly disabled pending local validation. Display the case's rule snapshots and coverage reasons.
- Render any API text as text. Fetch preview as an authenticated Blob, revoke its URL, and never put keys in URLs or persistent browser storage.

Current live URL and private key-entry procedure: [connected Vercel handoff](../integration/VERCEL_WEB_HANDOFF.md). A real 28.7 MB upload passed through the public origin in 60.625 s; independent second-PC verification remains open. The private bundle/archive and actual Windows runtime evidence are recorded in `docs/integration/A_TO_B_STATUS.md`; full disconnected qualification and useful recognition remain open.

Before public desktop distribution, prepare B's Electron/JavaScript notice inventory and a user-accessible third-party notices view or documentation. A's [release license inventory](release-licensing.md) identifies two supplemental license texts and remaining FFmpeg/native-library source obligations. The current binary candidate remains private and unapproved for public redistribution; do not mark the whole package reviewed from the new notice supplement.
