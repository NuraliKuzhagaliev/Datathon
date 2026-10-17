# Shared development instructions

Read README.md, forte_handoff/SHARED_CONTRACT.md, your master prompt, and packages/contracts/openapi.json before implementation. This repository currently contains a planning baseline, not a working application.

## Ownership

- Codex A: services/backend, infra, tools, assets/rules, docs/backend, docs/integration, Python dependencies and locks, root README.md, .gitignore, .env.example, packages/contracts.
- Codex B: apps/web, apps/desktop, docs/frontend, root package.json, pnpm-workspace.yaml, pnpm-lock.yaml, tsconfig.base.json and JavaScript dependencies.
- Keep forte_handoff unchanged as the planning snapshot. The working contract has ALREADY been copied to packages/contracts. Do not copy it again over newer changes.
- Do not overwrite another owner's files. Record requests in docs/backend/requests-for-b.md or docs/frontend/requests-for-a.md. Agree on contract revisions before implementation; update schema and fixtures together.
- A integrates codex/backend and codex/frontend into main at agreed checkpoints. Preserve existing changes, never force-push shared branches. Both developers begin from the same main baseline.

## Data boundaries

Keep supplied videos, frames, labels, event captions, private case reports, secrets, weights and runtime data outside version control. Do not send real footage or content-derived descriptions to cloud AI. Use synthetic fixtures for agent-visible UI work. Do not upload the original brief or local audit manifests without checking publication permission. Local human review and local model execution are required for real footage.

The public handoff excludes per-file audit/labels. When your prompt refers to them, obtain the original local team package; do not invent results. Aggregate research findings are not model accuracy measurements.

## Integration

The authority is packages/contracts/openapi.json and desktop-launch.schema.json. B generates client types into B-owned directories. No independent frontend/backend schemas. The original automatic verdict stays immutable when human review changes.

Use exactly two jury verdicts and real source timestamps/evidence in production. Synthetic fixtures require explicit development mode. No runtime cloud inference, face recognition or audio analysis. Implement the shared web/desktop architecture and document actual runnable commands only once available.

Follow the requested verification scope from each master prompt during implementation. This baseline itself has no application tests or executable service.
