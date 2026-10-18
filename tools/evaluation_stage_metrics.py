"""Aggregate gate counts only. Never emit captions, prompts, case IDs or frames."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from fact_pipeline import FACTS, TriggerFactPipeline


def score(run):
    public_registry = json.loads(
        (Path(__file__).resolve().parents[1] / "assets/rules/registry.json").read_text(
            encoding="utf-8"
        )
    )
    known_predicates = {
        rule["public"]["rule_id"]: set(rule["predicates"])
        for rule in public_registry["rules"]
    }
    known_statements = {
        rule["public"]["rule_id"]: rule["predicates"]
        for rule in public_registry["rules"]
    }
    known_gate_statements = {
        rule["public"]["rule_id"]: {
            "applicability": "The visible activity fits this scope: "
            + rule["public"]["applicability"],
            "context": "The relevant boundaries and area are sufficiently visible to establish this event: "
            + json.dumps(rule["predicates"], separators=(",", ":"))
            + ". Context requirement: "
            + rule["context"],
            "exclusion": "At least ONE of these exclusions actually applies to the proposed event: "
            + json.dumps(rule["public"]["exclusions"], ensure_ascii=False),
        }
        for rule in public_registry["rules"]
    }
    scene = Counter()
    facts = defaultdict(Counter)
    verification = defaultdict(Counter)
    atomic_support = Counter()
    atomic_predicates = defaultdict(Counter)
    atomic_gates = defaultdict(Counter)
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
            if value.get("support") in {"supported", "contradicted", "unobservable"}:
                support = value["support"]
                atomic_support[support] += 1
                statement = prompt.split("Statement=", 1)[-1].split(
                    "\nSource indices=", 1
                )[0]
                for rule_id, predicates in known_statements.items():
                    for key, public_text in predicates.items():
                        if statement == public_text:
                            atomic_predicates[rule_id][key + ":" + support] += 1
                for rule_id, gates in known_gate_statements.items():
                    for key, public_text in gates.items():
                        if statement == public_text:
                            atomic_gates[rule_id][key + ":" + support] += 1
                for rule in public_registry["rules"]:
                    if any(
                        statement
                        == "This specific exclusion applies to the proposed occurrence: "
                        + text
                        for text in rule["public"]["exclusions"]
                    ):
                        atomic_gates[rule["public"]["rule_id"]][
                            "individual_exclusion:" + support
                        ] += 1
                continue
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
                for key in known_predicates.get(rule_id, set()):
                    counts["unsupported_predicate:" + key] += (
                        predicates.get(key) is not True
                    )
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
                rule_ids = {
                    key
                    for questions in (FACTS, TriggerFactPipeline.QUESTIONS)
                    for key, question in questions.items()
                    if question in prompt
                }
                for rule_id in rule_ids:
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
        "independent_checks": dict(atomic_support),
        "independent_predicate_checks": {
            k: dict(v) for k, v in atomic_predicates.items()
        },
        "independent_scope_context_exclusion": {
            k: dict(v) for k, v in atomic_gates.items()
        },
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
