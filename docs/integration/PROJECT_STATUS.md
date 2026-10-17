# CashProof common engineering status

Updated 18 October 2026 during the owner's A+B audit. The formal work act and local evidence register are delivered separately in the owner's task outputs. Private footage, descriptions, per-file labels and keys are excluded from the repository.

## Implemented and checked

The shared React web/Electron interface uses OpenAPI 1.0.0 and the Python service. Jury upload/poll, operator review, immutable automatic results, source-linked evidence, preview timestamp mapping and server ZIP export are implemented. Real local model execution is verified separately from recognition quality.

Backend 0.3.2 explicitly selects the MOV demuxer, disables external track references and limits native decoding to local file/pipe protocols. Synthetic network-boundary tests observed no HTTP requests. All 40 unique dataset MOVs fully decoded without error; this is a compatibility check, not held-out model evaluation. The stable suite passed 28 tests (13.14 s).

Frontend checks passed: 38 unit, 20 development browser, 3 real-API/synthetic-model browser and 2 production CSP/demo-isolation scenarios. Desktop checks passed 5 security plus 5 resource-integrity tests; 4 shell scenarios and a separate new Connected executable smoke also passed. Counts are suites, not a count of independent requirements. Synthetic cases do not qualify model accuracy.

## Work completed by A in B's scope under the owner's instruction

- Generated full notices for ten installed frontend runtime packages and Open Sans, available offline in System and shipped in web/Windows resources. Electron/Chromium notices remain alongside the executable.
- Added contextual login/502/504 recovery messages in Russian and English.
- Fixed Electron's omission of a manifest-listed dotfile. The packaging hook verifies every listed file, restores only verified source bytes and rejects corruption, traversal, symlinks, Windows device paths and unlisted artifacts.
- Added separate build-output names, explicit backend selection and repeatable private verification destinations, preserving previous releases.
- Updated the acceptance matrix and five-minute demonstration/two-minute Q&A script. Rehearsal remains open.

## New private release candidate

The 0.3.2 portable bundle contains 20,531 listed files plus its manifest, 12,290,816,929 bytes. All 17 Python application files match clean runtime source a034fac203af202b16616b3a0b23d3bb3e0226d7. Every one of 20,532 ZIP entries was independently read, CRC checked and SHA-256 verified. The new ZIP is 7,323,884,572 bytes, SHA-256 f840bf51b4facdb915c2de455b3662c371bad3737d79ce3fc70238b229eed4f9. The immutable old 0.3.1 bundle/ZIP is preserved.

The full 0.3.2 Windows package completed a new real 28,718,927-byte development MOV using its own runtime/model: startup 34.636 s; analysis to visible result 25.882 s. Export, full ZIP CRC/hash checks, reload restoration and owned-backend shutdown passed. No external renderer origins were observed. The host remained connected; this is not disconnected qualification or real-event semantic acceptance.

The current local server uses this checked portable runtime, the original keys/case store and contract 1.0.0. Startup was 38.079 s. GPU experiments are finished. Keep the service host available and do not run another heavy model experiment alongside it.

## Model findings and decision

Production 0.3.2 completed all 28 development videos: TP=0, TN=13, FP=0, FN=15; recall 0/15, precision undefined, zero technical failures. Median latency was 3.628 s, sample p95 12.636 s, maximum 23.583 s. Reliable execution has not produced useful recognition.

EOS-fixed experimental Qwen3.5-4B accounted for all 28 development videos: 16 completed, 12 failed (4 deadline, 8 invalid output). Completed matrix TP=0, TN=7, FP=0, FN=9; six additional positives failed. End-to-end positive recall lower bound is 0/15. Completed median was 90.340 s, maximum 244.734 s; failed calls reached 270.543 s. This candidate is rejected for promotion. Earlier selected four-case results are historical probes, not the full-development result. Host engineering work overlapped inference, so these timings are observations under load, not an isolated speed benchmark.

Local structural analysis found 17 parseable experimental responses whose assessed frame was absent from their evidence list. An experimental-only normalization now includes that already-assessed bounded source frame, retaining all legal predicates/context/exclusion gates. Synthetic regression checks passed 13 with one optional-environment skip. No new private evaluation has qualified this fix; it is not in the stable model/runtime and does not alter the measured results above.

Validation 12 remains unused for inference/tuning. Human event-type labels and independent scene/view qualification are absent. No useful recognition, event F1, timestamp accuracy or generalization claim is made. See [model development](../backend/model-development.md).

## Deployment and remaining acceptance

The static site is https://cashproof-web.vercel.app . Its updated static frontend is published from the integration branch; all 11 public files match the checked local build. The old published temporary upstream is dead; two replacement API/health rewrites remain Vercel Draft, targeting range-journalism-louisiana-gym.trycloudflare.com. Publication still needs the outstanding action-time confirmation. Local readiness and historical HTTPS receipts do not establish current public API readiness.

A new checked static build is prepared. Vercel Drop creates a new project on each upload and cannot update this existing project; the existing project must use Git or CLI for repeatable updates. Never upload the whole local workspace or private release bundle to static hosting.

Useful detection, independent second-PC/network jury access, organizer acceptance of the relay, host-disconnected Windows execution, real-event semantic acceptance, required load/window availability and complete binary redistribution review remain open. The disconnected verifier changes no network settings and its CheckOnly mode starts no inference. Main remains unchanged; use codex/integration and draft PR #3 for review. See [executed evidence](verification.md).

Git deployment configuration is now saved in the existing Vercel project: the provided Datathon repository is connected, production tracks codex/integration, Node24/Other/root repository, frozen pnpm install, build:web and apps/web/dist. The checked-in vercel.json preserves the prior static security headers. The production build completed; the receipt below records current static verification. API/health routing remains separately unpublished Draft.

## Published static build, 18 October 2026

The existing production alias now serves the Git build from a1fa9d2a44a3c5c5953302460a8d75d6da09953e, deployment82s7f2A3sLFQg8eXEugSp9UG4zaR (Ready,18s). All11 public files (736,036bytes) were fetched anonymously and matched the corrected Windows build byte-for-byte; security headers and absence of actual credential values were checked. Public login rendered without accessing private cases. Explicit LF attributes preserve identical static/license bytes on Windows and Linux. The earlier prepared Drop directory is retained as historical and is not the final public fingerprint.

The owner prioritizes an accurate single service. API/health are two technical paths of that one service, not competing models. The latest response did not approve routing Publish; both rewrites remain Draft while recognition quality is unresolved. The local portable API/tunnel are ready, but current public API readiness is false. No claim of universally correct diagnosis is made.

Structural diagnosis of the production run: all93 stored screening responses contain empty event lists, and none of28 completed cases reaches verification. This localizes the observed bottleneck before the final legal gates. It does not prove the dataset's binary positives belong to the enabled paragraph22 category, because independent type labels are missing. Do not weaken final legal/context/exclusion gates merely to turn negatives into alerts. A different URL cannot change these results.
