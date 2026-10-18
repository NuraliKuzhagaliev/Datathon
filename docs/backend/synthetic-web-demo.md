# Synthetic Gemini lab in the website

Open `/#synthetic-lab` or **Gemini demo** in the sidebar/login screen. The lab is
available without an operator key or a running backend in both the production web
build and the shared desktop UI. It is separate from the authenticated case list,
upload, legal rules and jury API. Existing synthetic jury responses remain blocked
in production; the development-only UI fixture mode is unchanged.

## What actually runs

Eight regenerated geometric MP4s and explicitly whitelisted recorded Gemini 2.5
Flash observations are public static assets. The videos have no audio and contain
no supplied footage. The exporter regenerates each input and requires its SHA-256
to match the original synthetic experiment. It never copies supplied source videos.
Recorded answers are identified as recorded, with provenance timestamps. No Gemini
key is included or requested; no new cloud inference is performed by this page.

**Check geometry in browser** actually decodes the selected video, samples original
source timestamps, measures uncertain blue-square/red-line geometry and derives
crossings from observed side changes. It uses video pixels and model observations,
not reference event times. The reference is used only to score the final result.
An initial `on` followed by `right` alone never implies a crossing. An event needs
visible evidence of the preceding side. Ambiguous/missing shapes fail visibly.
Frame progress counts real processed frames. Changing scenario or stopping cancels
the work. Clicking an event seeks the video. Downloaded JSON keeps recorded Gemini
and locally computed results separate. No video or report is uploaded.

The blue/red pixel logic is specific to this geometric demonstration and must not
be represented as a bank-procedure detector or a repair to Gemini's own perception.
The page discloses the distinction between full recorded-response replay (8/8)
and the latest fresh API run (3/8 before free daily quota exhaustion).

## Build and verification

Committed public assets are sufficient for a fresh clone; generating them again is
not a prerequisite for building. `tools/export_synthetic_demo.py` is a local
authoring tool requiring the original *synthetic* experiment outputs:

```powershell
python tools/export_synthetic_demo.py --recordings-root <task-outputs/model-development>
pnpm build:web
pnpm check:ui
pnpm test:production
```

The new feature is loaded on demand as a separate JavaScript/CSS chunk. No new npm
dependency or external font, analytics endpoint or backend service was added.
English and Russian are supported. The main server-readiness indicator is replaced
by **Demo without API** only while viewing this lab.

Executed on Windows on 18 October 2026:

- Web typecheck and production build passed.
- 42 web unit tests passed, including video hashes, published data and pixel logic.
- 10 desktop unit tests passed (the symlink case required running outside the
  filesystem sandbox; it passed without changing the test or system settings).
- Complete backend suite: 159 passed, 1 skipped. The sandboxed import stalled;
  the successful full run used the existing qualified environment with downloads
  and Hugging Face telemetry disabled. No private model experiment was started.
- Three production browser tests passed, including original authentication/CSP
  checks and all eight lab scenarios with report download. The test asserts no
  cloud or jury API requests and no browser errors.
- An independent manual in-app-browser pass recomputed all eight scenarios and
  checked English rendering. The previously missed near-line event is 1.5 s;
  repeated events are 2.0/8.0 s, early 1.0 s, late 5.0 s, forward 3.0 s;
  reverse/near-miss/stationary controls have no requested events.

Before publication, staged content and unpublished history are checked against
local credential values without printing them. Private-data/runtime/weight/env
paths remain excluded. Only the eight regenerated public MP4s are included.

## Deployment

The existing Vercel `cashproof-web` project in the `lord-b46e` Hobby team tracks
`codex/integration` for Production and auto-assigns `cashproof-web.vercel.app`.
No domain, billing, secret, API rewrite or tunnel change is needed for this static
feature. GitHub publication and site deployment are verified separately; a pushed
commit alone is not evidence that the public site finished building.
