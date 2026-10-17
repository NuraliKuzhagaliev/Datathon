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

Comparison with already downloaded 4B checkpoints is next. A larger model or vendor benchmark alone cannot qualify CashProof. No change to a network route repairs these observed model failures.
