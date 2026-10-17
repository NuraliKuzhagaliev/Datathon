"""Two reversed synthetic sequences test video ordering, without private content."""

import json
from pathlib import Path
import time
from PIL import Image, ImageDraw, ImageFont
from jsonschema import validate


def verify(model, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (color, number) in enumerate([("red", 17), ("blue", 83)]):
        image = Image.new("RGB", (848, 464), color)
        ImageDraw.Draw(image).text(
            (424, 200),
            str(number),
            anchor="mm",
            fill="white",
            font=ImageFont.load_default(size=160),
        )
        path = directory / f"image-{i}.png"
        image.save(path)
        image.close()
        paths.append(path)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "first_color": {"type": "string", "enum": ["red", "blue"]},
            "last_color": {"type": "string", "enum": ["red", "blue"]},
            "first_number": {"type": "integer", "enum": [17, 83]},
            "last_number": {"type": "integer", "enum": [17, 83]},
        },
    }
    schema["required"] = list(schema["properties"])
    correct = 0
    for i, order in enumerate([[0, 0, 1, 1], [1, 1, 0, 0]]):
        frames = [
            {"id": f"f{n}", "timestamp_sec": t, "path": str(paths[k])}
            for n, (t, k) in enumerate(zip([10.0, 10.12, 13.5, 14.2], order))
        ]
        raw = model.infer(
            frames,
            "Read the background color and large number at the BEGINNING, then at the END of this ordered synthetic sequence. Keep beginning and end separate. Return JSON="
            + json.dumps(schema),
            time.time() + 90,
            output_schema=schema,
        )
        result = json.loads(raw)
        validate(result, schema)
        expected = {
            "first_color": "red" if i == 0 else "blue",
            "last_color": "blue" if i == 0 else "red",
            "first_number": 17 if i == 0 else 83,
            "last_number": 83 if i == 0 else 17,
        }
        correct += result == expected
        (directory / f"synthetic-result-{i}.json").write_text(
            json.dumps(result), encoding="utf-8"
        )
    aggregate = {
        "synthetic_temporal_grounding": True,
        "cases": 2,
        "complete_ordering_correct": correct,
        "passed": correct == 2,
        "meaning": "Synthetic input-order control only, not bank-event accuracy.",
    }
    (directory / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate), flush=True)
    return aggregate
