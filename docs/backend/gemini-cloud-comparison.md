# Cloud Gemini synthetic comparison — 18 October 2026

All model calls ran on Render against the same eight generated videos (five positive, three negative). No private competition footage or local GPU was used. Scoring references are applied only after inference. The primary task is left-to-right center crossings: the entire target-event list must match within 0.5 seconds. A separate all-direction score additionally checks right-to-left crossings. Independent pixel results are excluded from every score below. Technical failures are separate from model negatives.

| Variant | Completed / attempted | Target cases / all-direction cases | Video TP / TN / FP / FN | Technical failures | Mean processing seconds |
| --- | --- | --- | --- | --- | --- |
| Frame sides v3 | 8 / 8 | 7/8 target; 7/8 all directions | 4 / 3 / 0 / 1 | none | 14.262 |
| Context + zoom witnesses v5 | 3 / 4 | 1/3 target; 1/3 all directions | 2 / 0 / 1 / 0 | GEMINI_HTTP_503_NO_RETRY_OR_PAID_FALLBACK | 10.028 |
| Center prompt + HIGH thinking v6 | 1 / 2 | 0/1 target; 0/1 all directions | 0 / 0 / 0 / 1 | GEMINI_HTTP_503_NO_RETRY_OR_PAID_FALLBACK | 13.441 |
| Native video v7 | 8 / 8 | 7/8 target; 7/8 all directions | 5 / 3 / 0 / 0 | none | 13.668 |
| Native HIGH media v8 | 0 / 1 | not scored | 0 / 0 / 0 / 0 | INVALID_EVENT_SCHEMA_OR_TIMESTAMPS | n/a |
| Native HIGH + witnesses v9 | 0 / 1 | not scored | 0 / 0 / 0 / 0 | INVALID_EVENT_SCHEMA_OR_TIMESTAMPS | n/a |
| 3.1 visible reference + crossing projection v11 | 8 / 8 | 6/8 target; 6/8 all directions | 5 / 2 / 1 / 0 | none | 11.749 |
| 3.8 visible reference + crossing projection v11 | 8 / 8 | 8/8 target; 7/8 all directions | 5 / 3 / 0 / 0 | none | 18.909 |

Selected: **gemini-3.8-flash**, **native-reference-v11** — 8/8 target cases passed the timing criterion; 7/8 included every crossing in both directions; video TP/TN/FP/FN = 5/3/0/0.

The selected 3.8 first pass found all target events and times, including the near-line event at 1.5 s, with zero target false alarms. It omitted the auxiliary right-to-left return at 5 s in the repeated-crossing clip; its two target events at 2 and 8 s were correct. A bounded second model stage (v12) now reviews intervals between model-reported target events; it must locate the reverse crossing from the same video and provide temporal witnesses. No return is inferred from geometry or inserted from labels. This stage is verified separately and is not claimed as a new full eight-case run.

The visible-reference experiment detects only the stationary red calibration line, then draws that same reference through occlusion in the model input. It does not locate the blue object, search event times, read expected labels, or generate event answers. Every decoded source PTS is preserved. The browser discloses the transformation; original source and transformed model-input hashes are exported separately. It is a synthetic preprocessing experiment, not a claim about raw banking-video performance.

The reference profile requests only model-reported crossings, then projects their unchanged left-to-right times into the API event array. This removes a redundant field: a diagnostic response previously described a crossing but returned an empty event array. The untouched wire JSON is retained. Directions and timestamps must still pass the same strict witness checks; pixel geometry never supplies or corrects model times.

Native v7 detected all five positive videos and all three negatives, but timed the near-line crossing at 2.5 s instead of 1.5 s. This is one second of localization error, not a correct time. Frame-sides v3 instead missed that event; its errors on the other five matched events were about 0.2 s. No missing event is omitted from the case denominator.

Failures and rejected variants were retained. No provider retries or paid fallback were used. Automatic approval review initially rejected Gemini 3.8 because project Free Tier did not prove the selected model was free. Exact-model input/output prices were subsequently checked in the official pricing table, its Free Tier quota was checked in AI Studio, and a separate fresh key-bound model-price gate was implemented and tested. Only after those checks did configuration approval succeed. No billing or paid plan was enabled.

The suite is development data: eight simple geometric examples cannot establish 90% real-world accuracy, banking-rule understanding, unseen-camera performance or submission readiness. Real-video upload and the jury detector remain disabled. Free Tier verification expires after 30 minutes, and Render Free may sleep and lose ephemeral jobs.

References: [Gemini 3.1 Flash Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), [Free Tier pricing](https://ai.google.dev/gemini-api/docs/pricing), [media resolution](https://ai.google.dev/gemini-api/docs/generate-content/media-resolution).

Targeted production verification of v12: a fresh repeated-crossing job submitted through the main Vercel site completed on Render in 99.598 s using two model requests. Exported model crossings were left-to-right at 2.0 s, right-to-left at 5.0 s and left-to-right at 8.0 s, each with temporal witnesses. The target times were unchanged. This verifies the omitted auxiliary return; the other seven clips were not rerun under v12.
