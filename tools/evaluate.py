"""Same Pipeline as the production worker; labels never enter the inference path.

Input manifest is private JSON: [{path,label (0/1),times_sec:[],group,split}].
Only aggregate metrics are printed. Full predictions stay under private output.
"""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import time
import uuid
from cashproof.config import force_offline
from cashproof.inference.model import LocalQwen
from cashproof.inference.pipeline import Pipeline
from cashproof.rules import Registry
from cashproof.errors import ProcessingError


def ratio(a, b):
    return a / b if b else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--rules", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--verify-grounding", action="store_true")
    p.add_argument("--experimental-compact", action="store_true")
    p.add_argument("--native-video", action="store_true")
    p.add_argument("--experimental-fact-screen", action="store_true")
    p.add_argument("--experimental-trigger-screen", action="store_true")
    p.add_argument("--experimental-atomic-verifier", action="store_true")
    p.add_argument("--experimental-gguf-runtime", type=Path)
    p.add_argument("--gguf-provision-receipt", type=Path)
    p.add_argument("--experimental-precision", choices=["nf4", "bf16"], default="nf4")
    p.add_argument(
        "--experimental-screen-pixels",
        type=int,
        choices=[65536, 131072, 262144],
        default=65536,
    )
    p.add_argument(
        "--screen-wording", choices=["possible", "observed"], default="possible"
    )
    p.add_argument("--max-candidates", type=int, default=8)
    p.add_argument("--split", choices=["development", "validation"], required=True)
    p.add_argument(
        "--experimental-nf4",
        action="store_true",
        help="Development-only isolated adapter; not production qualification",
    )
    p.add_argument(
        "--max-videos",
        type=int,
        help="Development-only engineering sample; never a full evaluation",
    )
    p.add_argument(
        "--freeze-from",
        type=Path,
        help="Required for validation: completed development aggregate with the exact frozen configuration",
    )
    a = p.parse_args()
    if a.experimental_fact_screen:
        a.experimental_compact = True
    if a.experimental_trigger_screen and not a.experimental_fact_screen:
        raise ValueError(
            "Visual trigger proposals require explicit fact-screen experiment"
        )
    if a.experimental_atomic_verifier and not a.experimental_trigger_screen:
        raise ValueError(
            "Independent verifier requires the explicit trigger experiment"
        )
    if a.experimental_gguf_runtime and (
        not a.experimental_fact_screen or a.native_video or not a.gguf_provision_receipt
    ):
        raise ValueError(
            "GGUF requires fact screening, ordered images and pinned receipt"
        )
    if (
        a.experimental_precision != "nf4" or a.experimental_screen_pixels != 65536
    ) and not a.experimental_fact_screen:
        raise ValueError(
            "Precision/pixel comparison requires explicit fact-screen experiment"
        )
    experimental = a.experimental_nf4 or a.experimental_fact_screen
    if a.experimental_compact and not experimental:
        raise ValueError("Compact experiment requires the isolated NF4 adapter")
    if a.native_video and not a.experimental_compact:
        raise ValueError("Native video requires the isolated compact experiment")
    if a.screen_wording != "possible" and not a.experimental_compact:
        raise ValueError("Screening wording requires the isolated compact experiment")
    if experimental and a.split != "development":
        raise ValueError("Experimental adapter cannot open validation")
    if a.split == "validation" and not a.freeze_from:
        raise ValueError(
            "Validation requires --freeze-from with the frozen development configuration"
        )
    if a.max_videos is not None and (a.split != "development" or a.max_videos < 1):
        raise ValueError(
            "A partial run is permitted only for a positive development sample size"
        )
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    if not manifest.get("related_groups_reviewed"):
        raise ValueError(
            "A local reviewer must establish related-take groups before evaluation"
        )
    rows = manifest["rows"]
    by_hash = defaultdict(list)
    groups = defaultdict(set)
    for row in rows:
        source = Path(row["path"]).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise ValueError("Reviewed source hash changed")
        by_hash[digest].append(row)
        groups[row["group"]].add(row["split"])
    if any(len(g) > 1 for g in groups.values()):
        raise ValueError("Related group crosses splits")
    if any(len({r["split"] for r in rs}) > 1 for rs in by_hash.values()):
        raise ValueError("Exact duplicate crosses splits")
    if any(len({r["label"] for r in rs}) > 1 for rs in by_hash.values()):
        raise ValueError("Conflicting binary labels")
    force_offline()
    if a.experimental_gguf_runtime:
        from gguf_model import GGUFModel

        model = GGUFModel(
            a.model_dir,
            a.experimental_gguf_runtime,
            a.gguf_provision_receipt,
            a.output / "private-runtime",
            screen_pixels=a.experimental_screen_pixels,
        )
    elif experimental:
        from candidate_model import CandidateModel

        model = CandidateModel(
            a.model_dir,
            compact=a.experimental_compact,
            native_video=a.native_video,
            precision=a.experimental_precision,
        )
        if a.experimental_fact_screen:
            model.runtime_configuration.update(
                screening_max_pixels=a.experimental_screen_pixels,
                verification_max_pixels=min(262144, a.experimental_screen_pixels * 2),
                image_max_edge=848,
            )
            model.manifest["experimental_recipe"].update(model.runtime_configuration)
    else:
        model = LocalQwen(a.model_dir)
    if a.verify_grounding:
        if experimental:
            from grammar_controls import verify as verify_grammar

            grammar_check = getattr(model, "verify_grammar", None)
            grammar_result = (
                grammar_check(a.output / "synthetic-grammar-controls")
                if grammar_check
                else verify_grammar(model, a.output / "synthetic-grammar-controls")
            )
            if not grammar_result["passed"]:
                raise RuntimeError("Boolean grammar failed before private evaluation")
        from visual_grounding import verify

        if not verify(model, a.output / "synthetic-grounding")[
            "passed_number_color_controls"
        ]:
            raise RuntimeError(
                "Synthetic visual grounding failed before private evaluation"
            )
        if a.native_video or a.experimental_fact_screen:
            from temporal_grounding import verify as verify_temporal

            if not verify_temporal(model, a.output / "synthetic-temporal-grounding")[
                "passed"
            ]:
                raise RuntimeError(
                    "Synthetic temporal grounding failed before private evaluation"
                )
    if hasattr(model, "technical_calls"):
        model.technical_calls.clear()
    registry = Registry(a.rules)
    if not 1 <= a.max_candidates <= 32:
        raise ValueError("Candidate budget must be between 1 and 32")
    if a.experimental_fact_screen:
        from fact_pipeline import FactPipeline, TriggerFactPipeline

        pipeline_class = (
            TriggerFactPipeline if a.experimental_trigger_screen else FactPipeline
        )
        if a.experimental_atomic_verifier:
            from atomic_verifier import AtomicFactPipeline

            pipeline_class = AtomicFactPipeline
        pipeline = pipeline_class(model, registry, a.max_candidates)
    elif a.experimental_compact:
        from compact_pipeline import CompactPipeline

        pipeline = CompactPipeline(
            model, registry, a.max_candidates, screen_wording=a.screen_wording
        )
    else:
        pipeline = Pipeline(model, registry, a.max_candidates)
    if a.experimental_compact and a.verify_grounding:
        from screening_controls import verify as verify_screening

        controls = verify_screening(
            model,
            registry,
            a.output / "synthetic-screening-controls",
            wordings=[a.screen_wording],
            pipeline_class=type(pipeline) if a.experimental_fact_screen else None,
        )
        if not all(c["passes_negative_control"] for c in controls):
            raise RuntimeError(
                "Synthetic nonhuman negative control failed before private evaluation"
            )
        if a.experimental_fact_screen:
            from fact_screening_controls import verify as verify_facts

            if not verify_facts(
                model, a.output / "synthetic-fact-direction", type(pipeline)
            )["passed"]:
                raise RuntimeError(
                    "Synthetic positive/negative fact screen failed before private evaluation"
                )
        if a.experimental_gguf_runtime:
            from source_time_controls import verify as verify_source_time

            if not verify_source_time(
                model, a.output / "synthetic-source-time", type(pipeline)
            )["passed"]:
                raise RuntimeError(
                    "Generated end-to-end source-time control failed before private evaluation"
                )
        model.technical_calls.clear()
    if a.freeze_from:
        frozen = json.loads(a.freeze_from.read_text(encoding="utf-8"))
        if frozen.get("partial_evaluation") or frozen.get("split") != "development":
            raise ValueError("Freeze from a full development run")
        if (
            frozen["configuration"] != pipeline.configuration
            or frozen["manifest_sha256"]
            != hashlib.sha256(a.manifest.read_bytes()).hexdigest()
        ):
            raise ValueError(
                "Frozen implementation, rule/model assets or reviewed split changed"
            )
    run_id = uuid.uuid4().hex
    out = a.output / run_id
    out.mkdir(parents=True)
    tp = tn = fp = fn = failures = label_rows = 0
    latencies = []
    time_errors = []
    ambiguous = 0
    failure_codes = defaultdict(int)
    failure_types = defaultdict(int)
    failure_latency = []
    evidence_frames = 0
    selected = [rs for rs in by_hash.values() if rs[0]["split"] == a.split]
    if a.max_videos:
        selected = selected[: a.max_videos]
    selected_hashes = {rs[0]["sha256"] for rs in selected}
    torch_backend = getattr(model, "torch", None)
    if torch_backend is not None:
        torch_backend.cuda.reset_peak_memory_stats()
    for digest, rs in by_hash.items():
        if digest not in selected_hashes:
            continue
        label_rows += len(rs)
        directory = out / digest
        directory.mkdir()
        start = time.time()
        try:
            result, timeline = pipeline.run(
                Path(rs[0]["path"]),
                directory,
                digest[:32],
                start + 270,
                lambda **kwargs: None,
            )
            elapsed = time.time() - start
            if elapsed > 270:
                raise ProcessingError(
                    "DEADLINE_EXCEEDED",
                    "Development result exceeded production watchdog budget",
                )
            latencies.append(elapsed)
            (directory / "result.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            predicted = int(result["model_result"]["verdict"] == "violation")
            label = int(rs[0]["label"])
            tp += predicted == label == 1
            tn += predicted == label == 0
            fp += predicted == 1 and label == 0
            fn += predicted == 0 and label == 1
            annotations = [float(t) for row in rs for t in row.get("times_sec", [])]
            ambiguous += len(set(annotations)) > 1 and len(rs) > 1
            predicted_times = [
                e["timecode_sec"] for e in result["model_result"]["violations"]
            ]
            evidence_frames += sum(
                len(event["evidence_frames"])
                for event in result["model_result"]["violations"]
            )
            if predicted_times and label:
                # Each provided annotation is preserved, including both duplicate times.
                time_errors.extend(
                    min(abs(t - v) for v in predicted_times) for t in annotations
                )
        except Exception as error:
            failures += 1
            failure_types[type(error).__name__] += 1
            failure_latency.append(time.time() - start)
            oom = torch_backend is not None and isinstance(
                error, torch_backend.OutOfMemoryError
            )
            code = getattr(
                error, "code", "RESOURCE_EXHAUSTED" if oom else "PROCESSING_FAILED"
            )
            if oom:
                torch_backend.cuda.empty_cache()
            failure_codes[code] += 1
            (directory / "failure.json").write_text(
                json.dumps(
                    {
                        "technical_failure": True,
                        "error_code": code,
                        "error_type": type(error).__name__,
                    }
                ),
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "event": "evaluation_progress",
                    "split": a.split,
                    "finished": tp + tn + fp + fn + failures,
                    "total": len(selected),
                    "failed": failures,
                }
            ),
            flush=True,
        )
    completed = tp + tn + fp + fn
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    sorted_latency = sorted(latencies)
    metrics = {
        "run_id": run_id,
        "split": a.split,
        "partial_evaluation": bool(a.max_videos),
        "model_version": model.version,
        "configuration": pipeline.configuration,
        "rule_version": registry.version,
        "manifest_sha256": hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
        "unique_videos": completed + failures,
        "label_rows": label_rows,
        "completed": completed,
        "failed": failures,
        "failure_codes": dict(failure_codes),
        "failure_types": dict(failure_types),
        "failure_latency_sec": failure_latency,
        "positive_unique_denominator": sum(int(rs[0]["label"]) for rs in selected),
        "negative_unique_denominator": sum(1 - int(rs[0]["label"]) for rs in selected),
        "valid_evidence_frames": evidence_frames,
        "confusion_matrix_completed": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "precision": ratio(tp, tp + fp),
        "recall": recall,
        "balanced_accuracy_completed": (recall + specificity) / 2
        if recall is not None and specificity is not None
        else None,
        "failure_rate": ratio(failures, completed + failures),
        "recall_including_failures_lower_bound": ratio(
            tp,
            sum(int(rs[0]["label"]) for rs in selected),
        ),
        "timestamp_mae_sec": statistics.mean(time_errors) if time_errors else None,
        "timestamp_annotation_denominator": len(time_errors),
        "duplicate_positive_ambiguous_groups": ambiguous,
        "latency_sec": {
            "median": statistics.median(latencies) if latencies else None,
            "p95": sorted_latency[
                min(len(sorted_latency) - 1, int(0.95 * len(sorted_latency)))
            ]
            if latencies
            else None,
            "max": max(latencies) if latencies else None,
        },
        "type_accuracy": None,
        "peak_vram_bytes": torch_backend.cuda.max_memory_allocated()
        if torch_backend is not None
        else None,
        "vram_measurement": "PyTorch allocator"
        if torch_backend is not None
        else "Subprocess backend: peak not measured",
        "event_f1": None,
        "note": "Video labels provide neither event-type ground truth nor full event intervals. No generalization claim.",
    }
    (out / "aggregate.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    if hasattr(pipeline, "stage_counts"):
        metrics["stage_counts"] = pipeline.stage_counts
    if hasattr(model, "technical_calls"):
        calls = model.technical_calls
        (out / "technical-calls.json").write_text(
            json.dumps(calls, indent=2), encoding="utf-8"
        )
        metrics["inference_calls"] = len(calls)
        metrics["input_token_max"] = max(
            (c.get("input_tokens", 0) for c in calls), default=0
        )
        metrics["input_budget_failures"] = sum(
            c.get("input_budget_exceeded", False) for c in calls
        )
        metrics["native_video_calls"] = sum(c["native_video"] for c in calls)
        (out / "aggregate.json").write_text(
            json.dumps(metrics, indent=2), encoding="utf-8"
        )
    summary = {key: value for key, value in metrics.items() if key != "configuration"}
    summary["configuration_sha256"] = pipeline.configuration["configuration_sha256"]
    print(json.dumps(summary))
    if hasattr(model, "close"):
        model.close()


if __name__ == "__main__":
    main()
