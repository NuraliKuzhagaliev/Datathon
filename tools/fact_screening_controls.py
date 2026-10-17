"""Generated movement directions exercise fact screening and source-time selection."""

from types import SimpleNamespace
import json
import time
from PIL import Image, ImageDraw
from fact_pipeline import FactPipeline


def verify(model, directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "synthetic-questions.json"
    rule = {
        "predicates": {
            "crossing": "A drawn black stick figure crosses the red vertical line from LEFT to RIGHT during this sequence; right-to-left does not satisfy it."
        }
    }
    source.write_text(json.dumps(rule), encoding="utf-8")
    registry = SimpleNamespace(path=source, enabled={"TEST-MOVE": rule})
    frames = []
    for i, x in enumerate([120, 230, 410, 560]):
        picture = Image.new("RGB", (720, 400), "white")
        draw = ImageDraw.Draw(picture)
        draw.line((350, 20, 350, 380), fill="red", width=10)
        draw.ellipse((x - 20, 70, x + 20, 110), fill="black")
        draw.line((x, 110, x, 240), fill="black", width=10)
        draw.line((x - 40, 160, x, 130, x + 40, 160), fill="black", width=8)
        draw.line((x - 35, 320, x, 235, x + 35, 320), fill="black", width=8)
        path = directory / f"generated-{i}.png"
        picture.save(path)
        picture.close()
        frames.append(
            {"id": f"f{i}", "timestamp_sec": [0.0, 0.4, 1.2, 2.7][i], "path": str(path)}
        )
    rows = []
    for order, expected in [("forward", True), ("reverse", False)]:
        sequence = frames if expected else list(reversed(frames))
        sequence = [
            dict(f, id=f"f{i}", timestamp_sec=[0.0, 0.4, 1.2, 2.7][i])
            for i, f in enumerate(sequence)
        ]
        pipeline = FactPipeline(model, registry)
        result = pipeline.ask(sequence, None, time.time() + 90, directory / order)
        valid = all(
            e.event_frame_id in {f["id"] for f in sequence} for e in result.events
        )
        instant_correct = (
            [e.event_frame_id for e in result.events] == ["f2"]
            if expected
            else not result.events
        )
        rows.append(
            {
                "direction": order,
                "expected_event": expected,
                "returned_events": len(result.events),
                "source_indices_valid": valid,
                "first_supportable_instant_correct": instant_correct,
                "passed": bool(result.events) == expected and valid and instant_correct,
            }
        )
    value = {
        "synthetic_only": True,
        "controls": rows,
        "passed": all(r["passed"] for r in rows),
        "meaning": "Generated directional fact/index sanity check; not bank-event accuracy.",
    }
    (directory / "aggregate.json").write_text(
        json.dumps(value, indent=2), encoding="utf-8"
    )
    print(json.dumps(value), flush=True)
    return value
