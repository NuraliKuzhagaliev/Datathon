# CashProof common engineering status

Updated during the A+B audit on 17 October 2026. The formal work act and detailed local evidence register are in the owner's task outputs; they are not published as repository artifacts. No private footage, descriptions, per-file labels or keys belong in this status.

## Working implementation

The common React web/Electron interface uses the frozen OpenAPI 1.0.0 and the same Python service. Jury upload/poll, operator review, immutable automatic results, source-linked evidence, preview timestamp mapping and server ZIP export are implemented. A real development MOV has completed through the local API, the packaged Windows app and the historical public HTTPS route. These are execution results, not detection-accuracy qualifications.

Backend 0.3.2 explicitly selects the MOV demuxer, disables external MOV track references and limits native decoding to local file/pipe protocols. A generated playlist/direct-network test made no HTTP requests. The clean stable source passed 24 backend tests; the model-development tree passed 33 with one environment-dependent skip. Contracts and production model/rule selection are unchanged.

Frontend tests passed: 38 unit, 20 development browser, 3 production-API browser and 2 production browser scenarios. Desktop checks include 5 original security tests, 4 new resource-integrity tests, 4 Electron scenarios and a separate smoke of the new Connected executable. Synthetic models/inputs test engineering behavior, not Qwen accuracy. See [verification](verification.md) and [the acceptance matrix](../frontend/INTEGRATION_CHECKLIST.md).

## Gaps closed by A under the owner's audit instruction

- Added generated notices for ten installed frontend runtime packages and Open Sans, accessible offline from System and shipped in web/Windows resources. Electron/Chromium notices remain beside the EXE. Native/backend redistribution review remains separate.
- Corrected login diagnostics: missing API route no longer looks like a missing case; upstream/time-out errors give a recovery action.
- Found an Electron packaging omission: `assets/rules/.gitkeep` was excluded although listed in the trusted backend manifest. The packaging hook now restores only checked manifest-listed source bytes and hashes every packaged backend file. Corruption, traversal and symlinks fail the build. The prior standalone backend/ZIP is unchanged; the earlier full EXE was functionally exercised but its nested bundle was not hash-complete.
- Added separate build-output names and an explicit backend-directory option to preserve previous builds while qualifying a replacement.
- Updated B's integration state and prepared a five-minute demonstration/Q&A procedure. Team rehearsal is still open.

## Current qualification limits

The baseline full development evaluation missed every positive example. The EOS-fixed Qwen3.5-4B probe still has both a miss and a false alarm on its fixed four-case sample. A full development comparison is running separately. No experimental model is promoted, no held-out quality or different-camera claim is made, and validation has not been used for tuning. See [model development](../backend/model-development.md).

The static site is https://cashproof-web.vercel.app . The local API is paused with the owner's authorization for the GPU comparison. The old temporary Cloudflare upstream is dead; two replacement rewrites remain unpublished Vercel Draft. Historical HTTPS receipts are not current uptime. Publication needs the outstanding action-time approval. Original keys and case data are preserved.

Independent second-PC/network jury access, organizer acceptance of the relay, host-disconnected Windows execution, real-event semantic acceptance, useful recognition and complete native/binary redistribution review remain open. A prepared disconnected script does not change network settings or start inference in CheckOnly mode. Do not call the product fully qualified while these gates remain unresolved.

## Reproducible packaging

From the combined repository, after provisioning the checked backend folder:

```powershell
pnpm check:ui
pnpm build:web
node apps/desktop/scripts/package.mjs --connected --output-name connected-audit
node apps/desktop/scripts/package.mjs --backend-dir <qualified-bundle-folder> --output-name offline-audit
```

The ordinary `pnpm build:desktop` still consumes `releases/backend`. Copy the entire `win-unpacked` folder, not the EXE alone. A full package includes weights/runtime; Connected intentionally does not. File-integrity and runtime receipts are separate from a disconnected or model-quality qualification. Never replace an immutable archive or manifest to hide a failed check.
