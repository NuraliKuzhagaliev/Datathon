"""Local model calibration on generated color bars only; never reads real footage."""

import argparse
import json
from pathlib import Path
import time

from candidate_model import CandidateModel
from compact_pipeline import CompactPipeline
from cashproof import media
from cashproof.inference.pipeline import ScreenCandidate
from cashproof.rules import Registry
from synthetic_clip import create


def verify(
    model,
    registry,
    output,
    wordings=("possible", "observed"),
    show_output=False,
    pipeline_class=None,
):
    output.mkdir(parents=True, exist_ok=True)
    source = create(output / "generated-pattern.mov", rotated=True)
    timeline = media.decode_timeline(source, time.time() + 30)
    frames = list(
        media.extract(
            source,
            timeline,
            media.sample_indices(timeline),
            output / "frames",
            time.time() + 30,
        ).values()
    )
    results = []
    for wording in wordings:
        directory = output / wording
        directory.mkdir(exist_ok=True)
        pipeline = (
            pipeline_class(model, registry)
            if pipeline_class
            else CompactPipeline(model, registry, screen_wording=wording)
        )
        screen = pipeline.ask(frames, None, time.time() + 90, directory)
        key = next(iter(registry.enabled))
        rule = registry.enabled[key]
        candidate = ScreenCandidate(
            rule_id=key,
            event_frame_id=frames[0]["id"],
            frame_ids=[frames[0]["id"]],
            predicates={
                k: True
                for k in rule.get("candidate_triggers", list(rule["predicates"]))
            },
            applicable=True,
        )
        verification = pipeline.ask(frames, candidate, time.time() + 90, directory)
        eligible = sum(
            e.applicable
            and e.complete_context
            and not e.exclusion_present
            and all(e.predicates.values())
            for e in verification.events
        )
        metrics = {
            "wording": wording,
            "synthetic_no_humans": True,
            "screened_candidates": len(screen.events),
            "expected_screened_candidates": 0,
            "forced_verification_eligible": eligible,
            "passes_negative_control": len(screen.events) == 0 and eligible == 0,
            "configuration_sha256": pipeline.configuration["configuration_sha256"],
        }
        results.append(metrics)
        print(json.dumps(metrics), flush=True)
        if show_output:
            for path in sorted(directory.glob("*.json")):
                value = json.loads(path.read_text(encoding="utf-8"))
                print(
                    json.dumps(
                        {
                            "generated_synthetic_pattern_only": True,
                            "model_output": json.loads(value["output"]),
                        }
                    ),
                    flush=True,
                )
    (output / "aggregate.json").write_text(
        json.dumps(
            {
                "model_version": model.version,
                "synthetic_only": True,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-video", action="store_true")
    parser.add_argument("--show-synthetic-output", action="store_true")
    parser.add_argument(
        "--wordings",
        nargs="+",
        choices=["possible", "observed"],
        default=["possible", "observed"],
    )
    args = parser.parse_args()
    model = CandidateModel(args.model_dir, compact=True, native_video=args.native_video)
    verify(
        model,
        Registry(args.rules),
        args.output,
        args.wordings,
        args.show_synthetic_output,
    )


if __name__ == "__main__":
    main()
