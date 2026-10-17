# Frontend verification record

Date: 17 October 2026. All browser-visible data is synthetic. No supplied bank footage, frames or derived descriptions were inspected by cloud tools.

## Executed checks

| Check | Result |
| --- | --- |
| Type generation from OpenAPI 1.0.0 | Passed; 22 generated JSON validators and generated TypeScript declarations |
| TypeScript compilation | Passed |
| Unit checks | 38 passed: schema/integrity, time mapping, safe URLs, HTTP error/auth/download behavior, 7 text contrast pairs, immutable demo localization, English catalog coverage and interpolated errors |
| Desktop pure security checks | 3 passed: HTTPS/loopback policy, official-source policy, contained paths with spaces and Cyrillic |
| Development browser scenarios | 19 passed in Microsoft Edge: positive/negative/pending/failure states, multi-event keyboard navigation, rules, note/review, upload, media mapping, export, cleanup, modal focus, RU/EN switching and persistence, unchanged server data, blocked storage and English desktop/mobile layouts |
| Responsive evidence desk | Checked at 1440×900, 1366×768, 1024×768, 390×844; no page horizontal overflow; evidence and save action stay within width |
| Production browser scenarios | 2 passed: local assets/CSP/no demo and rejection of synthetic backend result |
| Web release build | Passed; static files emitted to apps/web/dist |

Counts refer to recorded successful runs; rerun the documented commands after integration. Screenshots and reports are build artifacts and are ignored by Git. Build commands clear `apps/web/dist`, so capture/report files can be regenerated with `pnpm test:e2e`.

## Visual review and repairs

Viewed synthetic screenshots for connection, case list, evidence desk, rules, mobile evidence, negative and pending states. Corrected a mobile grid minimum-width issue that initially clipped controls, constrained desktop grid rows so player controls/storyboard remained visible, improved evidence text sizing, made the review note expandable and restored keyboard focus after closing dialogs.

The requested Forte-inspired theme uses #A31551 for the primary action and #871044 on hover. Seven updated text/surface pairs pass 4.5:1, including status badges and secondary text. Open Sans is shipped locally with its license and Cyrillic/Kazakh coverage. Production checks verify that an actual Open Sans face loads and that no external asset requests occur. This is a focused contrast check, not a full WCAG certification or assistive-technology audit.

AJV runtime compilation initially conflicted with CSP. Validators now compile at build time into static modules; production works without `unsafe-eval`. The tests exercise original-to-preview scaling using a locally generated color-pattern MP4. They do not establish alignment on actual competition MOV files.

## Desktop runtime and packaging

Electron 44.9.0 was downloaded from its official release URL and checked against the checksum shipped in the npm package: SHA-256 `88e08039d0ef359bab9f674e8051fa103bd8628ea7c5a5e1daaa610a8a0c6931`.

`pnpm test:desktop` passed all 3 scenarios:

1. Launcher, missing-bundle message, connection to a synthetic local HTTP server, restricted preload bridge and renderer isolation, return to launcher.
2. A synthetic Node HTTP child launched through the exact manifest/args/environment handshake, from a directory with spaces and Cyrillic. The same production React build opened using the per-launch key; no key was stored in localStorage. After app shutdown, the child HTTP endpoint was unreachable.
3. The actual packaged `CashProof Connected.exe` launched successfully and displayed the missing-offline-resources state.

`pnpm build:desktop:connected` completed. Output: `apps/desktop/dist/connected/win-unpacked/CashProof Connected.exe`. Copy the entire `win-unpacked` folder, including `resources`, DLLs, locales and licenses. The EXE alone is insufficient.

Latest recorded automated checks: **65** (38 unit + 3 desktop pure security + 19 development browser + 2 production browser + 3 Electron runtime). Tests use a synthetic local process, not Python/model inference. The connected-only build cannot perform offline inference by itself. Full offline packaging requires A's bundle and is intentionally gated.

The initial automatic approval attempt for the final desktop check timed out before execution. One retry was approved and completed; there is no outstanding approval blocker.

## Not yet established

- Connection to Codex A's real API; upload → actual inference → actual evidence → actual review persistence/export.
- Performance, detection quality, current legal-source correctness or unseen-camera generalization.
- Real MOV source/preview synchronization, verified privately by a human.
- Actual model startup, GPU memory, worker crash recovery and offline processing on the RTX 4060 host.
- Public HTTPS reachability, judging-time availability or final branch merge.

Neither passing mocks nor a packaged UI proves these items.

## Forte theme rerun

After the requested palette/font update: 32 unit checks, 3 desktop security checks, 9 development browser scenarios, 2 production browser scenarios, and 3 Electron scenarios passed (49 total). Production explicitly loads Russian/Kazakh Open Sans subsets from local files. The connected Windows folder was rebuilt; screenshots of the cases page, evidence desk, mobile layout and desktop launcher were reviewed using synthetic data only.


## Russian UI, first-run guide and focused review

At that checkpoint, 55 checks passed: 34 web unit checks, 3 desktop security checks, 13 development browser scenarios, 2 production scenarios and 3 Electron runtime scenarios. Web and connected Windows builds completed successfully.

New scenarios verify the four-step guide, collapse/reopen across navigation within a session, demo entry, retained unsaved note when changing view, enlarged evidence stage, shortcut guards in note fields and dialogs, Escape closing a dialog before exiting focus mode, restored navigation after leaving a case, tablet/mobile bounds, and the same video element and playback position across a view switch. The text field now has an explicit accessible name. Demo translations preserve original shared fixtures, protocol IDs and the event/result relationship.

Screenshots reviewed: Russian guide, regular evidence desk, focused evidence at 1366px and 390px, desktop launcher. Real media integration and model quality still require participant A's backend. The Windows artifact remains a connected client.

## Russian / English interface

Added a persistent RU/EN selector, English interface catalog, translated demo presentation and local synthetic English JPEGs. Switching languages preserves the current case/event, selected decision, unsaved note and focus view. Browser tests verified that server-authored observation text, filenames, rule text, evidence image bytes and review payloads remain unchanged. Storage contains the language preference only; access keys are not persisted. A storage-disabled session can still switch language.

Viewed English cases and evidence screenshots at 1366px and 390px. No horizontal overflow or clipped language controls. Production checks cover the English interface after reload, local assets and the absence of a demo entry. Electron's synthetic local service test also switches to English, reloads, verifies persistence and returns to Russian. The native desktop connection launcher remains Russian; the review UI supports both languages.

Web and connected Windows builds completed. The web minifier reports a non-fatal 500 kB chunk advisory (main JS about 512 kB, 117 kB gzip). Windows packaging and Electron execution required the normal host process because the restricted process could not access the pnpm cache / Electron profile. No application sandbox or navigation policies were disabled.
