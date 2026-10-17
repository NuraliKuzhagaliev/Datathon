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


def ratio(a, b):
    return a / b if b else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--rules", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--split", choices=["development", "validation"], required=True)
    a = p.parse_args()
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
        by_hash[digest].append(row)
        groups[row["group"]].add(row["split"])
    if any(len(g) > 1 for g in groups.values()):
        raise ValueError("Related group crosses splits")
    if any(len({r["split"] for r in rs}) > 1 for rs in by_hash.values()):
        raise ValueError("Exact duplicate crosses splits")
    if any(len({r["label"] for r in rs}) > 1 for rs in by_hash.values()):
        raise ValueError("Conflicting binary labels")
    force_offline()
    model = LocalQwen(a.model_dir)
    registry = Registry(a.rules)
    pipeline = Pipeline(model, registry)
    run_id = uuid.uuid4().hex
    out = a.output / run_id
    out.mkdir(parents=True)
    tp = tn = fp = fn = failures = label_rows = 0
    latencies = []
    time_errors = []
    ambiguous = 0
    failure_codes = defaultdict(int)
    failure_latency = []
    evidence_frames = 0
    selected = [rs for rs in by_hash.values() if rs[0]["split"] == a.split]
    for digest, rs in by_hash.items():
        if rs[0]["split"] != a.split:
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
            failure_latency.append(time.time() - start)
            code = getattr(error, "code", "PROCESSING_FAILED")
            failure_codes[code] += 1
            (directory / "failure.json").write_text(
                json.dumps({"technical_failure": True}), encoding="utf-8"
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
        "model_version": model.version,
        "configuration": pipeline.configuration,
        "rule_version": registry.version,
        "manifest_sha256": hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
        "unique_videos": completed + failures,
        "label_rows": label_rows,
        "completed": completed,
        "failed": failures,
        "failure_codes": dict(failure_codes),
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
            sum(
                int(rs[0]["label"])
                for rs in by_hash.values()
                if rs[0]["split"] == a.split
            ),
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
        "event_f1": None,
        "note": "Video labels provide neither event-type ground truth nor full event intervals. No generalization claim.",
    }
    (out / "aggregate.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
