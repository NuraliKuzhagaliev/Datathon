# Executed verification — 17 October 2026

Shared baseline: `322afabd1daebc15d25846ac5fd4f62cd1c8c3d0`. Working contract 1.0.0 is unchanged. This is backend implementation evidence, not a completed competition submission.

Hardware observed locally: NVIDIA RTX 4060 Laptop GPU, 8,188 MiB VRAM, driver 595.97; Intel Core i7-13650HX; 16,777,711,616 bytes installed RAM. Python 3.12.14 is used for development. System Python 3.13.2 is not used for inference.

## Passed

- 17 backend tests passed in 5.30 seconds. They cover contract fixtures, exact JSON projections and auth; operator/jury scoping; corrupt upload, wrong field and body limit; five concurrent synthetic uploads with the conservative one-job admission setting (one 202, four 429); duplicate submission IDs and content hashes; durable queue expiry/restart recovery; immutable results, separate review persistence and checksummed export; actual VFR/rotation media decoding, source JPEGs and frame-by-frame preview mapping; different simultaneous event categories and renamed-input invariance through the production Pipeline using an explicitly injected synthetic model; one bounded JSON repair; full window coverage; and a real TCP startup with dynamic port and truthful 503 model readiness.
- All 40 unique private videos fully decoded locally with no failures. Longest duration 142.533 seconds, maximum measured decode 3.828 seconds, median 0.622 seconds. These are decoder measurements, not inference latency. 35 unique files have variable timing (the handoff's 37 count is over 42 label rows, including duplicates).
- Dataset reconciled: 42 files/rows, 40 unique SHA-256 hashes, 22 positive rows, 20 negative rows, two duplicate groups. Both positive duplicate times are preserved. Detailed data and labels are Git-ignored.
- A uv dependency lock was resolved for Python 3.11/3.12 and the pinned CUDA PyTorch index. Full GPU compatibility still requires the actual model smoke run.

The Windows sandbox blocks asyncio's internal loopback socket pair; HTTP tests were executed with loopback access enabled. The first rotation test found the fixture used an obsolete metadata-writing option. It was corrected to FFmpeg's `-display_rotation`; both displayed orientation and timestamp mapping now pass. No test bypass was added to production.

## Still required

- Finish the CUDA wheel/model downloads; verify model hashes; measure genuine local model output, peak VRAM, latency and longest-video analysis. Synthetic model tests do not establish model quality.
- Local reviewer establishes related-take groups and taxonomy privately, then locks the evaluation split. The initial 28/12 unique allocation is provisional; no blind validation or accuracy number is claimed.
- Measure production inference for five queued/admitted uploads. The current admission test establishes bounded behavior only.
- B's web/desktop builds, cross-machine integration, genuine upload-to-result, and the portable offline bundle with all prerequisites.
- Process/network-isolated model run after provisioning. Offline flags and missing-model tests alone do not establish this.
- Team-controlled public HTTPS routing, organizer clarification if any relay handles footage, an external-network jury-style POST/poll, and uptime. No domain or inbound route was supplied.

Only the paragraph 22 detector is enabled experimentally. Five other candidate rules remain disabled. There is no claim of broad category coverage, completed public deployment, desktop readiness, accuracy, p95 inference latency or competition qualification.
