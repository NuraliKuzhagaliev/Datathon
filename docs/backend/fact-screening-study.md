# Visual-fact screening study, 18 October 2026

The owner explicitly requested model improvement, useful violation detection and source-timeline localization after the common audit. Work is isolated on `codex/model-development`. Production 0.3.2, contracts, stable integration and immutable releases remain preserved. The idle owned API was stopped for the authorized GPU window; original credentials/cases and the Cloudflare process remain preserved. Restore the stable service after the study.

## Baseline and selection method

Production completed all 28 development inputs but returned TP0/TN13/FP0/FN15. All 93 stored screening responses had empty event lists; no case reached verification. The previous Qwen3.5-4B six-rule candidate had no successful positive detections and 12 technical failures. Its small four-case results are not a full-development result. The binary labels lack event types/full intervals, and positives are not independently established as paragraph-22 events.

Test a mandatory observed/absent/unclear fact screen before the existing legal verifier, using actual source indices. Compare already provisioned weights first, including unquantized 2B BF16. Keep all final predicates, applicability, complete-context and exclusion gates. No image, caption or per-case semantic output is exposed to the cloud agent. A candidate failing synthetic positive/negative controls cannot proceed to private evaluation. Pixel/modal comparisons use frozen source and explicit fingerprints. Selected four-case probes are exploratory; only a later full-development candidate may be considered for promotion. Validation remains closed for tuning.

Timing assessment includes all positive annotated instants, retaining both supplied times on the ambiguous duplicate. Report one-to-one annotation coverage within 2/5/10 seconds including misses and technical failures in the denominator. A nearest-time MAE on detected positives alone is conditional and must not stand alone. These point annotations do not support event F1 or type accuracy.

## Implemented engineering changes

- `fact_pipeline.py`: mandatory fact questions, actual-frame indices, explicit uncertainty and overflow failure; unchanged inherited final verifier.
- A separate visual inventory describes the actual input before action questions. Pictures without people do not become human-action candidates. This is a measured visual gate, not a dataset-name or label lookup.
- `candidate_model.py`: development-only BF16 option restricted to the pinned 2B checkpoint; NF4 remains the default for previous experiments. Larger unquantized loading is rejected.
- `evaluation_time_metrics.py`: aggregate timing coverage with one-to-one matching and explicit conditional-MAE denominator.
- New tests cover exact source mapping, unclear/negative outputs, fabricated indices, bounded unused negative indices, overflow and inclusion of misses/failures in timing coverage. The shared legal rejection tests remain in place.

## Controls before private inference

The first mandatory-fact BF16/native attempt passed grammar, number/color/figure controls (4/4) and reversed color/number ordering (2/2), but hallucinated some action checks on generated color bars and produced unused negative indices. It stopped with MODEL_OUTPUT_INVALID before any private case. This is a failed control, not an accuracy result.

After adding the visual inventory and ignoring bounded unused negative indices, the same no-people control passed with zero candidates and zero eligible forced verifications. A new generated stick-figure direction control then failed: both forward and reverse crossing produced events. Both directions are required; a detector that always emits candidates does not pass. No private evaluation occurred in either attempt.

A smaller two-field question was compared with the same 2B BF16 weights. Ordered images correctly selected source index2 for the forward crossing but incorrectly returned true/index1 for the reversed crossing. Native video returned true/index1 in both directions, including a wrong source instant for the forward crossing. Thus the existing color-order control is insufficient to qualify action direction or action-time grounding. The four synthetic responses are not bank-event measurements. Further candidates must pass exact direction and source-index checks before private tests; native pairwise temporal tokenization must not be mistaken for one token per original frame.

The 4B NF4 checkpoint passed the simple forward/reverse check with ordered images, including the exact first supportable source index. Native video missed the forward action. Independent short fact questions were therefore tested with ordered images at 131072 screening pixels and 262144 verification pixels. The actual fact pipeline passed all generated controls before private inference, but the four-case development probe completed zero inputs: one deadline failure and three processing failures. Thirty inference calls had a median of 5.49 seconds and a maximum of 51.67 seconds; only one verification call was attempted and no completed assessment was produced. This candidate is rejected, rather than treating failed cases as negatives. No validation footage was opened.

## Pinned local GGUF experiment

The official Qwen3-VL-8B-Instruct-GGUF checkpoint at revision `f982a07559d4a2f6c8744d840bf6fccab30eea96` is stored on D. Its Q4_K_M language weights and F16 visual projector were checked against the official full SHA256/size metadata. The official llama.cpp b11715 CUDA 12.4 runtime archives and all 55 extracted files were verified. No driver was changed. Redundant C-drive archives and the byte-identical C-drive 2B model copy were removed after verification; the previous 2B path points to the preserved immutable release copy on D.

`gguf_model.py` starts and terminates only its owned loopback runtime, with a fresh private in-memory key, no web UI, no external image URLs, bounded images/context/output and no context shifting. Images are embedded locally with their original source timestamps. A deadline closes the client and stops the owned model process, and a truncated generation cannot count as a clean result. Runtime errors expose only technical codes; response bodies and model semantics remain private. No cloud API is used. Peak GPU memory is explicitly unmeasured for this subprocess backend, rather than reporting a misleading PyTorch allocator value.

The initial 8B engineering probe uses the same four development inputs and unchanged final legal verifier. It must pass the same generated visual, reversed-order, nonhuman-negative and exact action/source-index controls before private inference. Four cases are exploratory, not full-development or held-out qualification. A larger model or vendor benchmark alone cannot qualify CashProof.
