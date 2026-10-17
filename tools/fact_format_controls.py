"""Public synthetic format/modality ablation; no dataset or labels are read."""

import argparse
import json
from pathlib import Path
import time
from candidate_model import CandidateModel


def verify(model, frames, directory):
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "left_to_right": {"type": "boolean"},
            "first_supported_index": {
                "anyOf": [{"type": "integer", "enum": list(range(4))}, {"type": "null"}]
            },
        },
        "required": ["left_to_right", "first_supported_index"],
    }
    rows = []
    for native in (False, True):
        model.native_video = native
        for reverse in (False, True):
            sequence = list(reversed(frames)) if reverse else frames
            sequence = [
                dict(f, id=f"f{i}", timestamp_sec=[0.0, 0.4, 1.2, 2.7][i])
                for i, f in enumerate(sequence)
            ]
            prompt = (
                "These are four ordered frames numbered 0,1,2,3. A black stick figure and a stationary red vertical line are visible. "
                "Does the figure cross that line specifically FROM LEFT TO RIGHT (not right to left)? "
                "If yes, select the first frame where the figure has reached the RIGHT side after being on the LEFT. "
                "If no, set left_to_right=false and first_supported_index=null. Answer only this directional question. "
                "Do not describe the sequence. Source frames: index0 at0.0s,index1 at0.4s,index2 at1.2s,index3 at2.7s. JSON="
                + json.dumps(schema)
            )
            raw = model.infer(sequence, prompt, time.time() + 90, output_schema=schema)
            value = json.loads(raw)
            (
                directory
                / f"{'native' if native else 'images'}-{'reverse' if reverse else 'forward'}.json"
            ).write_text(
                json.dumps({"synthetic_only": True, "response": value}),
                encoding="utf-8",
            )
            rows.append(
                {
                    "native": native,
                    "reverse": reverse,
                    "response": value,
                    "direction_correct": value["left_to_right"] is not reverse,
                    "instant_correct": value["first_supported_index"]
                    == (None if reverse else 2),
                }
            )
    summary = {
        "synthetic_only": True,
        "rows": rows,
        "model_version": model.version,
        "meaning": "Exact source-index and directional sanity controls, not bank-event accuracy.",
    }
    (directory / "aggregate.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", required=True, type=Path)
    p.add_argument("--frames-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--precision", choices=["bf16", "nf4"], default="bf16")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    model = CandidateModel(a.model_dir, compact=True, precision=a.precision)
    frames = [
        {
            "id": f"f{i}",
            "timestamp_sec": [0.0, 0.4, 1.2, 2.7][i],
            "path": str(a.frames_dir / f"generated-{i}.png"),
        }
        for i in range(4)
    ]
    verify(model, frames, a.output)
