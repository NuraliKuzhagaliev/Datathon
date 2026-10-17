"""Aggregate gate counts only. Never emit captions, prompts, case IDs or frames."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from fact_pipeline import FACTS


def score(run):
    scene = Counter()
    facts = defaultdict(Counter)
    verification = defaultdict(Counter)
    records = invalid = cases = 0
    for case in run.iterdir():
        if not case.is_dir() or not (case / "configuration.json").is_file():
            continue
        cases += 1
        for path in (case / "private-inference").glob("*.json"):
            records += 1
            record = json.loads(path.read_text(encoding="utf-8"))
            try:
                value = json.loads(record["output"])
                if not isinstance(value, dict):
                    raise ValueError()
            except (ValueError, TypeError):
                invalid += 1
                continue
            prompt = record["prompt"]
            if "people_visible" in value:
                scene["calls"] += 1
                scene["people_visible"] += value["people_visible"] is True
                scene["visibility_limited"] += value.get("visibility_limited") is True
                continue
            rule_id = next(
                (key for key in FACTS if prompt.startswith("Candidate=" + key + ".")),
                None,
            )
            if rule_id and "predicates" in value:
                counts = verification[rule_id]
                counts["calls"] += 1
                counts["applicable"] += value.get("applicable") is True
                counts["complete_context"] += value.get("complete_context") is True
                counts["exclusion_present"] += value.get("exclusion_present") is True
                predicates = value["predicates"]
                all_supported = bool(predicates) and all(
                    v is True for v in predicates.values()
                )
                counts["all_predicates_supported"] += all_supported
                counts["eligible"] += (
                    all_supported
                    and value.get("applicable") is True
                    and value.get("complete_context") is True
                    and value.get("exclusion_present") is False
                )
            elif "observed" in value:
                rule_id = next(
                    (key for key, question in FACTS.items() if question in prompt), None
                )
                if rule_id:
                    counts = facts[rule_id]
                    counts["calls"] += 1
                    counts["observed"] += value.get("observed") is True
                    counts["visibility_limited"] += (
                        value.get("visibility_limited") is True
                    )
                    counts["overflow"] += value.get("overflow") is True
    return {
        "private_cases": cases,
        "inference_records": records,
        "unparseable_records": invalid,
        "scene_inventory": dict(scene),
        "fact_questions": {k: dict(v) for k, v in facts.items()},
        "verification_gates": {k: dict(v) for k, v in verification.items()},
        "limits": "Aggregate model gate diagnostics, not independent ground truth. Raw semantics stay private.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(args.run)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
