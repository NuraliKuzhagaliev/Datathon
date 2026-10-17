# CashProof web and desktop — Codex B

**Актуализация общего аудита 17 октября 2026.** Исторические утверждения ниже относятся к состоянию B до интеграции. Полный backend-комплект и реальные прогоны на A уже существуют. Текущая доступность API, качество модели и открытые проверки описаны в [общем акте](../integration/PROJECT_STATUS.md); они не подтверждаются ранними синтетическими тестами.

## Setup

Use Node 24.13+ and pnpm 11.25.0. From the repository root:

```powershell
pnpm install --frozen-lockfile
pnpm generate:api
pnpm dev:web
```

Web development URL: `http://127.0.0.1:5173`. The normal screen asks for an operator API key held in memory. The development server proxies `/api` and `/health` to `http://127.0.0.1:8000`.

To connect to a different team backend during development:

```powershell
$env:CASHPROOF_DEV_BACKEND = 'https://YOUR-TEAM-SERVER'
pnpm dev:web
```

Use only a trusted team server. Browser production requests use relative URLs, so serve the static web build and API from the same origin. Do not put keys in environment variables embedded in a web build, URLs, localStorage or Git.

## Interface languages

Use **RU / EN** in the top bar to change language without reloading. Russian is the default. The language preference is stored as `cashproof.language` in localStorage for the current web origin; access keys and case data are not stored there. With browser storage blocked, switching still works for the current session. The shared Windows review interface uses the same selector; its preference is scoped to the connected origin (a new local service port is a new origin). The native connection launcher remains in Russian.

Navigation, guide, upload, review controls, status/error messages, accessibility labels, dates and page metadata are localized. Changing language preserves the active event, unsaved note, decision and focus view. Backend observations, filenames, legal source text, evidence images and user notes retain their original content. Only explicitly synthetic demo presentation has translated sample text/images. API enums and payloads do not change.

Translation code: `apps/web/src/i18n/`; English catalog: `en.json`. New UI copy needs a catalog entry. Development-only demo adapters stay in `src/mocks/` and are eliminated from the production build. Synthetic images can be regenerated with `python apps/web/scripts/generate-demo-frames.py --language ru` or `--language en`.

## Synthetic demonstration

Development only: `http://127.0.0.1:5173/?demo=1`. Deep-link evidence: `http://127.0.0.1:5173/?demo=1#case=synthetic-positive`.

The persistent banner identifies synthetic fixtures. No inference runs; upload is disabled. Demo human review persists only in memory. MP4 replay and real ZIP export require the backend; their absence is displayed honestly. Production builds remove the demo import branch and reject synthetic CaseDetail responses.

## Commands

| Command | Result |
| --- | --- |
| `pnpm generate:api` | TypeScript types and CSP-safe validators generated from contract 1.0.0 |
| `pnpm dev:web` | Vite web dev server, fixed port 5173 |
| `pnpm build:web` | Typechecked static build in `apps/web/dist` |
| `pnpm check:ui` | Generated types, TypeScript, unit contract/time tests, desktop security tests |
| `pnpm test:e2e` | Synthetic browser scenarios using installed Microsoft Edge |
| `pnpm test:production` | Build and verify no production demo, no external assets, strict CSP and rejection of synthetic server results |
| `pnpm test:desktop` | Electron launcher/connected smoke and synthetic local-process lifecycle; does not test inference |
| `pnpm test:integration` | A's unchanged FastAPI/store/media/export + production UI, with a scripted synthetic model; requires the setup below |
| `pnpm dev:desktop` | Build web, start Electron mode selector |
| `pnpm build:desktop:connected` | Windows folder without inference resources |
| `pnpm build:desktop` | Windows folder including A's backend bundle; refuses missing bundle |

The E2E configuration uses Edge (`channel: msedge`). Install Edge or explicitly change that local test setting to an available Playwright browser. No real videos are used by any automated browser test.

## Code map

- `apps/web/src/api/generated/`: generated TypeScript and schema validators, never edit manually.
- `apps/web/src/api/client.ts`: authenticated typed HTTP transport, XHR upload progress, Blob media/export, timeouts.
- `apps/web/src/api/validation.ts`: contract and cross-field integrity checks.
- `apps/web/src/features/`: upload, evidence/replay/review, rule library and provenance drawer.
- `apps/web/src/styles/app.css`: shared responsive visual system and reduced-motion handling.
- `apps/web/src/mocks/`: explicit development-only fixtures; no backend implementation.
- `apps/desktop/`: Electron launcher, scoped bridges, process lifecycle, URL/path checks and packaging.
- `apps/web/tests/`: unit and browser checks; generated color-pattern test video is stored as text base64 for reproducibility.

## Desktop modes

**On this computer:** requires A's complete portable backend bundle under `releases/backend` in development or the packaged `resources/backend` folder. Validated launch.json, random key, loopback dynamic port, HTTP handshake, model readiness. The local Python process is hidden. No runtime model download.

**Team server:** opens the chosen HTTPS origin. Loopback HTTP is allowed for local development. Enter the operator key in the web UI. Connected mode starts no local GPU service and is not offline inference.

The local wrapper displays startup errors when the runtime/weights are missing. Web and desktop use the same static build. `contextIsolation`, renderer sandbox and disabled Node integration are enforced. IPC checks the sending frame and origin. External navigation is restricted; official source links require explicit user action. The app does not keep API keys between launches. Deleting a case requires an explicit UI confirmation.

Packaging is an unsigned Windows application folder, not a signed installer. Copy the whole `win-unpacked` folder, not only the EXE. Full model/offline qualification must take place on the RTX 4060 machine.

Current verified connected output: `apps/desktop/dist/connected/win-unpacked/CashProof Connected.exe`. It was launched in the packaged-app smoke test. The local lifecycle fixture only proves the process contract; it does not qualify any AI model or GPU.

## Scope and limitations

Tests with mock HTTP prove client behavior. The separate [backend integration run](BACKEND_INTEGRATION.md) exercises A's actual API, storage, media and export with a scripted model and generated video. Neither verifies Qwen accuracy or the deployed GPU service. The frozen shared fixtures are unchanged; development demo copies have Russian and English presentation labels and original geometric frames. Actual display text is rendered as text, without interpreting HTML. Rule sources in an event always use that case's immutable snapshot.

The browser authenticates the list endpoint at connection. In-memory credentials require re-entry after refresh. Hash routes retain only an opaque job ID, never a key. The server's persisted case list restores access to ongoing work.

See `requests-for-a.md` for real integration dependencies and `QA.md` for executed checks. Do not claim offline inference or legal correctness from a frontend build.

## Demonstration and integration handoff

- [Three-minute demonstration](PITCH.md): Russian narration, exact actions and timings, honest current demo, substitutions after real integration, rehearsal plan and fallback.
- [Integration checklist](INTEGRATION_CHECKLIST.md): inputs needed from A, connection setup, 18 real-service acceptance checks, ownership, API matrix and result template. All real integration checks remain unverified.
- [Backend integration evidence and setup](BACKEND_INTEGRATION.md): reproducible synthetic checks against A's source, dependency boundaries and remaining release gates.
- [Message prepared for A](HANDOFF_TO_A.txt): copyable handoff text; not sent automatically. Frontend is published in `codex/frontend`; A owns the final merge into `main`.

## Implementation references

- [Electron security guidance](https://www.electronjs.org/docs/latest/tutorial/security): isolated sandboxed renderers, restricted IPC/navigation and external URL policy.
- [Vite guide](https://vite.dev/guide/): local development and static release build.
- [openapi-typescript](https://openapi-ts.dev/introduction): client types generated from the shared OpenAPI source.
## Current visual theme

Updated at the user's request on 17 October 2026 to match the colors and typography observed on [ForteBank's website](https://forte.kz/ru): Open Sans, white panels, #1D1D1D primary text, #6C6C6C secondary text and #A31551 burgundy accents. Hover #871044 and pale rose #F9EDF2 are application adaptations. CashProof retains its own name and icon.

Open Sans variable WOFF2 subsets (Latin, Cyrillic, extended Cyrillic including Kazakh) are bundled in `apps/web/public/fonts` and `apps/desktop/assets/fonts`, together with the SIL OFL license. There are no runtime font requests to ForteBank or Google. Web and desktop use the same React styles; the native mode chooser uses the same font and palette. Video evidence keeps a dark neutral stage for image contrast.

## Getting started and focused review

The cases page shows four steps: upload, inspect events, check the source, save the human decision. The instruction can be collapsed and reopened; this preference lasts for the current app session and stores no data in browser storage. In explicit development demo mode its action opens a synthetic example; in the connected app it opens the actual upload dialog.

Completed cases offer “Сосредоточенная проверка”: it hides navigation, expands the video area and retains the selected event and the current note. It does not remount the player or review form. “Обычный вид” or Escape restores navigation; leaving a case also restores the normal view. Unsaved notes are not persisted by changing views.

Keyboard help is available next to the view switch: J/О next event, K/Л previous event, F/А view switch, ? help, Escape close the dialog before exiting focus mode. Letter shortcuts do not run in editable fields, during composition, with Ctrl/Alt/Meta, on key repeat, or while a dialog is open. The view switch also works on tablet and mobile.

Fixed UI labels and demo observations support Russian and English. Protocol IDs, file extensions, versions and user/server text retain their original values. `src/mocks/localize.ts` translates fresh copies of the frozen fixtures and supplies an English presentation adapter; real API responses and shared contracts are untouched. Four original geometric JPEGs in each language are generated by `scripts/generate-demo-frames.py` (Pillow and Windows Arial), checked into the development-only module, and excluded from the release by Vite's DEV guard.

