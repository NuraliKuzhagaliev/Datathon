"""Post-inference proposal-time coverage; annotations never enter the predictor."""

import argparse
import json
from pathlib import Path

from evaluation_time_metrics import matches


def proposals(case):
    times = set()
    verification_times = set()
    invalid = 0
    for file in (case / "private-inference").glob("*.json"):
        record = json.loads(file.read_text(encoding="utf-8"))
        if record["prompt"].startswith("Candidate="):
            for marker in ("Source indices=", "Frame indices="):
                if marker not in record["prompt"]:
                    continue
                legend = json.JSONDecoder().raw_decode(
                    record["prompt"].split(marker, 1)[1]
                )[0]
                verification_times.update(
                    float(item["source_seconds"]) for item in legend
                )
                break
        try:
            answer = json.loads(record["output"])
        except (ValueError, TypeError):
            continue
        if not isinstance(answer, dict):
            continue
        joint = isinstance(answer.get("checks"), dict) and all(
            isinstance(row, dict) and ("events" in row or "state" in row)
            for row in answer["checks"].values()
        )
        if joint:
            try:
                legend = json.JSONDecoder().raw_decode(
                    record["prompt"].split("Source indices=", 1)[1]
                )[0]
                if any(
                    row.get("overflow", False) is not False
                    or row.get("state") not in {None, "observed", "absent", "unclear"}
                    for row in answer["checks"].values()
                ):
                    raise ValueError()
                selected = [
                    event["onset_index"]
                    for row in answer["checks"].values()
                    for event in row.get("events", [])
                ]
                if any(
                    type(i) is not int or not 0 <= i < len(legend) for i in selected
                ):
                    raise ValueError()
                times.update(float(legend[i]["source_seconds"]) for i in selected)
            except (KeyError, IndexError, ValueError, TypeError):
                invalid += 1
            continue
        if answer.get("observed") is not True:
            continue
        try:
            legend = json.JSONDecoder().raw_decode(
                record["prompt"].split("Source indices=", 1)[1]
            )[0]
            indices = answer["indices"]
            if (
                answer.get("overflow") is not False
                or not indices
                or any(type(i) is not int or not 0 <= i < len(legend) for i in indices)
            ):
                raise ValueError()
            selected = [float(legend[i]["seconds"]) for i in indices]
        except (KeyError, IndexError, ValueError, TypeError):
            invalid += 1
            continue
        times.update(selected)
    return sorted(times), invalid, sorted(verification_times)


def score(manifest, run, split):
    groups = {}
    for row in manifest["rows"]:
        if row["split"] == split:
            groups.setdefault(row["sha256"], []).append(row)
    evaluated = positives = negatives = failed_positives = annotated = invalid = 0
    pos_with = neg_with = proposal_instants = 0
    counts = {t: 0 for t in (2, 5, 10)}
    available = {t: 0 for t in (0.5, 1, 2)}
    no_verification = 0
    for digest, rows in groups.items():
        case = run / digest
        if not case.is_dir():
            continue
        evaluated += 1
        predicted, bad, verification_times = proposals(case)
        invalid += bad
        if not rows[0]["label"]:
            negatives += 1
            neg_with += bool(predicted)
            continue
        positives += 1
        failed_positives += (case / "failure.json").is_file()
        pos_with += bool(predicted)
        proposal_instants += len(predicted)
        annotations = [float(t) for row in rows for t in row.get("times_sec", [])]
        no_verification += not verification_times
        annotated += len(annotations)
        for tolerance in counts:
            counts[tolerance] += matches(annotations, predicted, tolerance)
        for tolerance in available:
            available[tolerance] += sum(
                any(abs(t - v) <= tolerance for v in verification_times)
                for t in annotations
            )
    return {
        "split": split,
        "partial_evaluation": evaluated != len(groups),
        "evaluated_unique_videos": evaluated,
        "expected_split_unique_videos": len(groups),
        "positive_videos": positives,
        "negative_videos": negatives,
        "positive_failed_jobs": failed_positives,
        "positive_videos_with_proposals": pos_with,
        "negative_videos_with_proposals": neg_with,
        "unique_proposal_instants_on_positive_videos": proposal_instants,
        "annotated_positive_instants": annotated,
        "one_to_one_proposal_matches": {
            f"within_{t}_sec": n for t, n in counts.items()
        },
        "proposal_annotation_coverage": {
            f"within_{t}_sec": n / annotated if annotated else None
            for t, n in counts.items()
        },
        "invalid_positive_proposal_records_excluded": invalid,
        "positive_cases_without_saved_verification_frame_legends": no_verification,
        "verification_frame_availability_matches": {
            f"within_{t}_sec": n for t, n in available.items()
        },
        "verification_frame_annotation_availability": {
            f"within_{t}_sec": n / annotated if annotated else None
            for t, n in available.items()
        },
        "limits": "Visual proposals before legal gates/budget admission are not jury violations. Diagnostic coverage may include failed jobs; final-result timing coverage includes failures as misses. Identical proposal times across rules/repairs are deduplicated. Verification-frame availability measures supplied timestamps, not recognition or sufficient evidence. These are untyped point annotations, not exhaustive event ground truth.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["development", "validation"], required=True)
    args = parser.parse_args()
    result = score(
        json.loads(args.manifest.read_text(encoding="utf-8")), args.run, args.split
    )
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
