# Executed verification — 17 October 2026

Shared baseline: `322afabd1daebc15d25846ac5fd4f62cd1c8c3d0`. Working contract 1.0.0 is unchanged. This is backend implementation evidence, not a completed competition submission.

Hardware observed locally: NVIDIA RTX 4060 Laptop GPU, 8,188 MiB VRAM, driver 595.97; Intel Core i7-13650HX; 16,777,711,616 bytes installed RAM. Python 3.12.14 is used for development. System Python 3.13.2 is not used for inference.

## Passed

- 19 backend tests passed in 6.79 seconds with FFmpeg 9.0.2. They cover contract fixtures, exact JSON projections and auth; operator/jury scoping; corrupt upload, wrong field and body limit; five concurrent synthetic uploads with the conservative one-job admission setting (one 202, four 429); duplicate submission IDs and content hashes; durable queue expiry/restart recovery, including an interrupted job across a real TCP process restart; injected worker OOM remaining a technical failure; immutable results, separate review persistence and checksummed export; actual VFR/rotation media decoding, source JPEGs and frame-by-frame preview mapping; different simultaneous event categories and renamed-input invariance through the production Pipeline using an explicitly injected synthetic model; one bounded JSON repair; full window coverage; and dynamic-port startup with truthful 503 missing-model readiness. Scripted/injected models validate engineering behavior only.
- All 40 unique private videos fully decoded locally with no failures. Longest duration 142.533 seconds, maximum measured decode 3.828 seconds, median 0.622 seconds. These are decoder measurements, not inference latency. 35 unique files have variable timing (the handoff's 37 count is over 42 label rows, including duplicates).
- Dataset reconciled: 42 files/rows, 40 unique SHA-256 hashes, 22 positive rows, 20 negative rows, two duplicate groups. Both positive duplicate times are preserved. Detailed data and labels are Git-ignored.
- Pinned Qwen assets are provisioned and all hashes checked. PyTorch 2.8.0+cu128, torchvision 0.23.0+cu128, Transformers 4.57.1 and BF16/SDPA executed on the real GPU. Dependencies are locked; HTTP stack is FastAPI 0.143.3 / Starlette 1.8.0 / python-multipart 0.0.32. The initial smoke exposed torchvision as a required processor dependency; it was added and exercised.
- Real five-frame synthetic model smoke: load 18.70 seconds, inference 3.085 seconds, peak allocated VRAM 4,461,305,344 bytes; Python networking completely denied, zero network attempts. This is model execution evidence, not model accuracy.
- Real API longest-video run (`544a0103dead41f7befbf891f43e7f1e`): one accepted, one completed, no failures; 142.533-second source, upload response 0.305 seconds, upload-to-result 173.008 seconds, startup 27.415 seconds, peak allocated VRAM 5,010,976,256 bytes. All windows completed. Private case contents were not inspected by the coding agent.
- Real API five-queued synthetic run (`ae227f79664742d88ea54b25b9358465`): five accepted, five completed, no failures; four-second rotated VFR test pattern; upload responses 0.280–0.282 seconds; completion 4.361–10.942 seconds including queue wait (median 7.403), startup 23.883 seconds; peak allocated VRAM 4,624,069,120 bytes. This does not establish a five-long-video envelope. Production default remains one pending/active job.
- Both API runs imposed a Python socket/DNS guard denying external destinations while allowing loopback. That is process-level evidence only: native libraries and the host NIC were not disabled. No claim of OS-level offline qualification is made.
- Local human returned the reviewed grouping manifest. It passed source-row preservation, duplicate and group separation checks: 28 development unique videos (15 positive/13 negative), 12 validation (6/6), 40 groups. Manifest SHA-256 is `01e260b05f1e92161b567447d89c9bd81bb5bfba37b9842e33313fdec6e07a48`. Development evaluation is running; no accuracy is claimed before aggregate results exist.
- Portable candidate `releases/backend-0.2.0-rc1` assembled with Python runtime, installed CUDA packages, all model assets, FFmpeg/ffprobe 9.0.2, package/license inventory, launch contract and 20,486 file hashes. Assembly is not offline execution proof. Public redistribution review remains open; FFmpeg source revision information is included, but a link alone is not a complete corresponding-source distribution.

The Windows sandbox blocks asyncio's internal loopback socket pair; HTTP tests were executed with loopback access enabled. The first rotation test found the fixture used an obsolete metadata-writing option. It was corrected to FFmpeg's `-display_rotation`; both displayed orientation and timestamp mapping now pass. No test bypass was added to production.

The first larger-visual-context longest-video run failed at the watchdog after 272.09 seconds with `DEADLINE_EXCEEDED`; it did not return a clean verdict. The measured successful configuration uses 14/2-second screening windows, at most 16 images per call, lower per-stage pixel budgets and sparse wide context anchors with denser action sampling. This speed improvement has not established equal or better detection quality. The earlier compact-prompt synthetic vertical slice completed in 3.162 seconds; performance changes are not a quality ablation.

## Backend 0.3.0 development findings

The first full development attempt on 0.2.0 was interrupted after four finished videos: one completed negative (TN=1), three technical failures. Structural diagnostics found truncated JSON and oversized evidence-ID lists. Private content was not returned to the coding chat. This partial attempt is not an accuracy estimate.

0.3.0 adds local grammar-constrained JSON and action-trigger gating. Twenty backend tests pass (9.27 seconds), including the new normal-context/no-action regression. The five-queued synthetic API run `8610c726d0724105bc457a0c387f15f6` completed 5/5 with no failures: admission 0.267–0.269 seconds, completion 4.852–9.935 seconds, median 7.397; startup 29.175 seconds. Python external networking was denied.

The same four development videos then completed without technical failures (`a9434a2e50ca45a68c85b9a38603e8d7`), but both positives were missed: TP=0, TN=2, FP=0, FN=2; recall 0/2, precision undefined (no positive predictions), balanced accuracy 0.5, no timestamp matches. Median processing 9.639 seconds, max 13.955. Detection quality is inadequate. The positive duplicate's two annotations remain separate; event-type ground truth is absent.

| Engineering experiment, same four development videos | Completed | Technical failures | Observed detection result |
| --- | --- | --- | --- |
| 0.2.0 baseline, interrupted after four | 1/4 | 3/4 | One TN; insufficient completed class coverage |
| 0.3.0 grammar + action-trigger gating | 4/4 | 0/4 | TP 0, TN 2, FP 0, FN 2 |

This is a combined engineering comparison, not an isolated temporal-verification quality ablation. Full 28-video development evaluation is running. A second private local review page contains the 15 positive development examples for human taxonomy/applicability review; validation remains unopened. Expanding rules or asserting model quality before that evidence would be unsupported.

Portable 0.3.0-rc1 assembled with 20,526 hashed files. The final candidate will also include the complete model/registry configuration snapshot and bytecode-disabled launch environment. Neither assembly nor successful imports qualifies it as offline-tested. The Windows Firewall verification script parses successfully, but current Windows privileges are not Administrator, so its OS-level test has not run.

## Remaining qualification gates

- Complete development evaluation, establish useful private taxonomy/coverage with local review, freeze configuration, then run locked validation. No broad accuracy or blind-validation number is claimed yet.
- Measure five queued long-video jobs if that concurrency is required. Current short-video results do not support increasing production admission.
- Execute the portable runtime itself, OS-level offline qualification, archive/checksum, B's web/desktop builds and cross-machine integration. B's application directories have no implementation in this checkout.
- Team-controlled public HTTPS routing, organizer clarification if any relay handles footage, an external-network jury-style POST/poll, and uptime. No domain or inbound route was supplied.

Only the paragraph 22 detector is enabled experimentally. Five other candidate rules remain disabled. There is no claim of broad category coverage, completed public deployment, desktop readiness, accuracy, population p95 inference latency or competition qualification. A single longest-video success does not guarantee the deadline for every video or queue load.
