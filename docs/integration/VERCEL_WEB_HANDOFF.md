# Vercel frontend handoff

**Maintenance snapshot, 17 October 2026:** local API paused with user approval for GPU evaluation. The old Cloudflare upstream below no longer resolves. Replacement `range-journalism-louisiana-gym.trycloudflare.com` is prepared in Vercel Draft, not published. Do not use historical successful receipts as current readiness. [Common audit](PROJECT_STATUS.md).

Public production URL: https://cashproof-web.vercel.app . Dashboard: https://vercel.com/lord-b46e/cashproof-web . Account nuralikuzhagaliev, team Lord, Hobby.

Published 17 October 2026 using Vercel Drop to Deploy: only the freshly built static frontend, nine public assets plus deployment configuration, 672,855 bytes total. Frontend source e03e5a96324fd36afd2b85872a5f7d3c2806971d, integrated at 0549cf420511402c6d8a01f292917828b339d3f1. The build used Node 24.19.0 / pnpm 11.25.0. No B-owned source was changed. Main remains 322afabd1daebc15d25846ac5fd4f62cd1c8c3d0.

Anonymous HTTPS returned 200 for all nine assets; every remote body matched the local SHA-256. The deployed login page rendered with zero browser console errors. Both local credential values were checked absent from every asset before upload. No private footage, frames, inference output, keys, weights or backend runtime was uploaded as static deployment content. The generated deployment-specific URL uses Vercel authentication; use the public production alias above for ordinary viewing. No deployment protection was changed.

The live route is browser or jury client → Vercel CDN external rewrite → Cloudflare Tunnel → A's loopback port 8000 → the existing local GPU worker. Video and API-key headers transit Vercel/Cloudflare; inference remains on A's RTX 4060. The human explicitly authorized this original real-video route after the named-provider/privacy disclosure. Organizer approval is not recorded; this is a temporary integration route, not a claim of competition approval or guaranteed availability. No cloud AI receives case content.

Two project-level **CDN → Routing Rules** are published independently of the static deployment:

| Rule | Regex source | Rewrite destination | Response header |
| --- | --- | --- | --- |
| bae0c7ed-7800-40b0-9ded-9d15319104e3 | `^/api/(.*)$` | `https://warned-bizarre-marker-jerry.trycloudflare.com/api/$1` | `Cache-Control: no-store` |
| b690a687-2196-42dc-b86c-4dbf55f0f389 | `^/health/(.*)$` | `https://warned-bizarre-marker-jerry.trycloudflare.com/health/$1` | `Cache-Control: no-store` |

Use regex mode and `$1`. The first attempted pattern-style parameter was forwarded literally and caused the reported JSON 404; the published regex rules correct it. Credentials are supplied by each client in `X-API-Key`, never embedded in routing configuration or frontend assets.

Measured public path:

- `/health/ready`: 200, ready=true / mode=server / contract_version=1.0.0; local startup 24.796 s. This is runtime readiness, not detection accuracy.
- Missing credentials rejected; operator authenticated; jury rejected from operator-only case listing. API/export responses use no-store.
- New generated rotated/VFR color-bar MOV: 163,478 bytes, real local model, 1.234 s admission and 5.937 s full upload-to-result. UI detail and exported ZIP accessible; four ZIP entries fully CRC checked.
- New integrity-checked development-only real MOV: 28,718,927 bytes, one accepted / one completed / zero failures; 40.218 s admission including transmission and 60.625 s full client upload-to-result. Jury schema/source-PTS range valid. Private results remain local; only technical aggregates are reported here.

Both clients ran on A's host and reached the public HTTPS origin. A separate computer/network has not been verified. B should now run the agreed integration checklist from its own client. Successful transport does not qualify recognition: baseline development recall remains 0/15; real positive/multiple-event correctness and review remain unqualified.

Existing distinct operator/jury credentials remain in ignored `runtime-data/team-server/credentials.json` on A's computer. The human enters operator locally in the login form; jury is for upload/poll only. Deliver keys privately without pasting them into coding chats, issues or source. A cloud coding reviewer must not inspect authenticated real case lists, video, evidence or semantic reports; use generated synthetic cases for agent-visible work.

Keep A's computer awake, connected and its team server/tunnel running. Do not start heavy model experiments alongside the service. This temporary tunnel changes address on restart, requiring both routing rules to be updated and verified again. No unattended restart or uptime guarantee is configured. The backend admits one active/pending job and returns 429 + Retry-After on saturation. Cloudflare's ordinary 100 MB upload allowance is below the backend's 128 MiB limit; measured 28.7 MB inputs fit. Do not advertise 128 MiB end-to-end support. Jobs use asynchronous POST/poll; the measured public job remained within 300 s.

Git-based automatic redeployment is not configured. B can publish a new checked `apps/web/dist` to this same project, or separately configure its Git source to the agreed integration branch with Node 24, pnpm 11.25.0, root build command `pnpm build:web` and output `apps/web/dist`. The old main branch has no implemented web frontend. Never upload the whole local working directory, which also contains ignored private data and models.

Receipts in the parent task outputs: `VERCEL-PUBLIC-BUILD.json`, `VERCEL-HTTPS-VERIFICATION.json`, `VERCEL-CONNECTED-VERIFICATION.json`, `VERCEL-REAL-UPLOAD-VERIFICATION.json`, `VERCEL-CONNECTED-ROUTES.json`, `VERCEL_FOR_B.txt` and public readiness screenshot `CashProof-Public-Health.png`. Preserve the project routing rules when updating static assets. Backend runtime source remains 4a69e19d99b1fbf0e35b6991b0a68a88bd5f0d8d, version 0.3.1 / contract 1.0.0.
