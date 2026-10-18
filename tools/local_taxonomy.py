"""Automated private development taxonomy; never human-reviewed ground truth.

Annotation windows are used for development review only. This tool and its label
manifest are not imported or included in the production runtime.
"""

import argparse
import hashlib
import json
from pathlib import Path
import time
from cashproof import media
from cashproof.inference.model import LocalQwen
from cashproof.rules import Registry
from jsonschema import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    registry = Registry(args.rules)
    model = LocalQwen(args.model_dir)
    selected = {}
    for row in data["rows"]:
        if row["split"] == "development" and row["label"] == 1:
            selected.setdefault(row["sha256"], []).append(row)
    rows = []
    failed = 0
    supported = set()
    rules = [
        {
            "rule_id": key,
            "applicability": value["public"]["applicability"],
            "predicates": value["predicates"],
            "exclusions": value["public"]["exclusions"],
        }
        for key, value in registry.rules.items()
    ]
    for digest, annotations in selected.items():
        directory = args.output / digest
        directory.mkdir(exist_ok=True)
        source = Path(annotations[0]["path"])
        timeline = media.decode_timeline(source, time.time() + 30)
        times = sorted(
            {float(t) for row in annotations for t in row.get("times_sec", [])}
        )
        for number, t in enumerate(times or [timeline.duration / 2]):
            target = directory / str(number)
            target.mkdir(exist_ok=True)
            try:
                start, end = max(0, t - 12), min(timeline.duration, t + 12)
                points = [start + (end - start) * i / 10 for i in range(11)] + [
                    max(0, t - 1),
                    t,
                    min(timeline.duration - 0.001, t + 1),
                    0,
                    max(0, timeline.duration - 0.001),
                ]
                frames = list(
                    media.extract(
                        source,
                        timeline,
                        sorted({timeline.nearest(p) for p in points}),
                        target / "frames",
                        time.time() + 30,
                    ).values()
                )
                schema = {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "rule_id",
                        "applicable",
                        "trigger_visible",
                        "complete_context",
                        "exclusion_present",
                        "frame_ids",
                        "observation",
                        "limitations",
                        "unsupported_category",
                    ],
                    "properties": {
                        "rule_id": {
                            "type": "string",
                            "enum": list(registry.rules) + ["UNSUPPORTED"],
                        },
                        "applicable": {"type": "boolean"},
                        "trigger_visible": {"type": "boolean"},
                        "complete_context": {"type": "boolean"},
                        "exclusion_present": {"type": "boolean"},
                        "frame_ids": {
                            "type": "array",
                            "maxItems": 3,
                            "items": {
                                "type": "string",
                                "enum": [f["id"] for f in frames],
                            },
                        },
                        "observation": {"type": "string", "maxLength": 300},
                        "limitations": {"type": "string", "maxLength": 200},
                        "unsupported_category": {"type": "string", "maxLength": 100},
                    },
                }
                prompt = (
                    "Candidate=private development review interval. Describe only actions actually visible across these frames, then classify the main observable action against the verified rule list. The source annotation is not proof of any legal category. Choose UNSUPPORTED for a different action, unclear scope, or no supportable listed category. Do not force a match. No identity, intent or authorization inference. Complete context requires visible sequence boundaries and relevant customer/work area. Keep any private description brief. Return JSON only.\nRules="
                    + json.dumps(rules, ensure_ascii=False)
                    + "\nSchema="
                    + json.dumps(schema)
                )
                raw = model.infer(
                    frames, prompt, time.time() + 180, output_schema=schema
                )
                (target / "private-model-output.json").write_text(
                    json.dumps({"prompt": prompt, "output": raw}, ensure_ascii=False),
                    encoding="utf-8",
                )
                result = json.loads(raw)
                validate(result, schema)
                rows.append(
                    {"sha256": digest, "annotation_time_sec": t, "model_review": result}
                )
                if (
                    result["rule_id"] != "UNSUPPORTED"
                    and result["applicable"]
                    and result["trigger_visible"]
                    and result["complete_context"]
                    and not result["exclusion_present"]
                ):
                    supported.add(result["rule_id"])
            except Exception:
                failed += 1
        print(
            json.dumps(
                {
                    "event": "private_automated_taxonomy_progress",
                    "videos_finished": len({r["sha256"] for r in rows}),
                    "videos_total": len(selected),
                    "failed_intervals": failed,
                }
            ),
            flush=True,
        )
    result = {
        "provenance": "Automated local model review only; user explicitly did not perform human taxonomy review",
        "human_reviewed": False,
        "model_version": model.version,
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "rows": rows,
        "supported_rule_ids": sorted(supported),
        "failed_intervals": failed,
    }
    (args.output / "private-taxonomy.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "private_automated_review_complete": True,
                "unique_development_videos": len(selected),
                "annotation_intervals": len(rows),
                "failed_intervals": failed,
                "supported_rule_category_count": len(supported),
                "human_reviewed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
