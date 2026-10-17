# Vercel frontend handoff

Updated 18 October 2026. The current state below supersedes historical successful 0.3.1 HTTPS measurements.

Production alias: https://cashproof-web.vercel.app . Existing project: cashproof-web, Lord Hobby (lord-b46e), account nuralikuzhagaliev. The published static build is the old e03e5a9 frontend. The local API is restored from checked portable backend 0.3.2, original credentials retained; it is not yet reconnected to the production alias.

## Routing publication pending

The two project-level CDN rules still publish the dead warned-bizarre-marker-jerry.trycloudflare.com upstream. Prepared replacements remain unpublished Draft:

| Rule | Regex source | Prepared destination |
| --- | --- | --- |
| bae0c7ed-7800-40b0-9ded-9d15319104e3 | `^/api/(.*)$` | `https://range-journalism-louisiana-gym.trycloudflare.com/api/$1` |
| b690a687-2196-42dc-b86c-4dbf55f0f389 | `^/health/(.*)$` | `https://range-journalism-louisiana-gym.trycloudflare.com/health/$1` |

Both use Cache-Control: no-store. Clients provide X-API-Key; no key is in routing or static assets. Prior automatic review rejected Publish and requires fresh action-time confirmation; the owner's last response deferred publication until model work was finished. No later approval is assumed. After authorized publication, verify fresh health, auth scopes and a new synthetic POST/poll/detail/export through the public alias. Do not infer current uptime from historical receipts.

Video and API-key headers traverse Vercel and Cloudflare; inference stays on the local RTX 4060. The owner allowed that transport after disclosure; organizer acceptance is not recorded. Keep this host, portable API and tunnel alive. Tunnel restart changes its hostname; update both rules and verify again. No uptime guarantee is configured. Independent second-PC/network access remains untested.

## Static update prepared

The new checked static build has 11 public assets plus vercel.json, 737,189 bytes, with local frontend notices and no keys/private case material. Vercel Drop cannot update an existing project: each drop creates another project. Update this same project using Git or authenticated CLI, preserving the production alias and CDN rules. Proposed Git source is the supplied public NuraliKuzhagaliev/Datathon repository, branch codex/integration. Main contains only the old baseline and must not be used for this build.

Build configuration: root repository, Node 24, pnpm 11.25.0, install pnpm install --frozen-lockfile, build pnpm build:web, output apps/web/dist, framework Other. No backend secrets, weights, cases, private release or entire workspace are uploaded. Do not broaden GitHub app access to unrelated private repositories.

## Current limits

Stable backend 0.3.2 completed all 28 development videos with no technical failures but TP0/TN13/FP0/FN15. Experimental Qwen3.5-4B is rejected; validation is unused. Real positive/multiple-event semantic acceptance is open. Model readiness is not recognition qualification.

Historical 0.3.1 HTTPS receipts documented a synthetic analysis/export in 5.937 s and a 28.7 MB real MOV in 60.625 s, both from this host; they are retained as historical evidence only. Current local portable startup is 38.079 s. New full Windows 0.3.2 real-MOV analysis/export passed locally while the host was connected. The admission limit remains one active/pending task with 429 + Retry-After; no arbitrary-video/queue deadline guarantee or five-long-video qualification is made.

Keys are in ignored runtime-data/team-server/credentials.json. Enter operator locally; jury only uploads/polls. Never paste values or real-case outputs into coding chats, issues or Git. See [common status](PROJECT_STATUS.md) and [A to B](A_TO_B_STATUS.md).
