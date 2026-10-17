"""Aggregate source-time scoring after inference; annotations never enter prediction."""

import argparse
import json
from pathlib import Path
import statistics


def matches(annotations, predictions, tolerance):
    """Maximum one-to-one point matches, including distinct ambiguous annotations."""
    assigned = {}

    def visit(i, seen):
        for j, value in enumerate(predictions):
            if j in seen or abs(annotations[i] - value) > tolerance:
                continue
            seen.add(j)
            if j not in assigned or visit(assigned[j], seen):
                assigned[j] = i
                return True
        return False

    return sum(visit(i, set()) for i in range(len(annotations)))


def score(manifest, run, split):
    grouped = {}
    for row in manifest["rows"]:
        if row["split"] == split:
            grouped.setdefault(row["sha256"], []).append(row)
    totals = {t: 0 for t in (2, 5, 10)}
    annotated = positive_cases = failed = predicted_positive_instants = 0
    errors = []
    for digest, rows in grouped.items():
        case = run / digest
        if not case.exists():
            continue
        if not rows[0]["label"]:
            continue
        positive_cases += 1
        times = [float(t) for row in rows for t in row.get("times_sec", [])]
        annotated += len(times)
        if (case / "failure.json").exists():
            failed += 1
            continue
        result = json.loads((case / "result.json").read_text(encoding="utf-8"))
        predictions = [
            float(v["timecode_sec"]) for v in result["model_result"]["violations"]
        ]
        predicted_positive_instants += len(predictions)
        for tolerance in totals:
            totals[tolerance] += matches(times, predictions, tolerance)
        if predictions:
            errors.extend(min(abs(t - v) for v in predictions) for t in times)
    return {
        "split": split,
        "positive_cases_accounted": positive_cases,
        "positive_technical_failures": failed,
        "annotated_instants_total": annotated,
        "predicted_instants_on_positive_videos": predicted_positive_instants,
        "one_to_one_annotation_matches": {
            f"within_{t}_sec": n for t, n in totals.items()
        },
        "annotation_coverage": {
            f"within_{t}_sec": n / annotated if annotated else None
            for t, n in totals.items()
        },
        "nearest_annotation_mae_on_positive_predictions_sec": statistics.mean(errors)
        if errors
        else None,
        "nearest_annotation_mae_denominator": len(errors),
        "event_f1": None,
        "event_type_accuracy": None,
        "limits": "Point annotations are not exhaustive typed event ground truth. Both duplicate-positive times remain separate. Failures and undetected positive annotations stay in coverage denominator. Nearest MAE excludes positives without predictions and must not stand alone. Partial runs remain partial.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", choices=["development", "validation"], required=True)
    args = parser.parse_args()
    result = score(
        json.loads(args.manifest.read_text(encoding="utf-8")), args.run, args.split
    )
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
