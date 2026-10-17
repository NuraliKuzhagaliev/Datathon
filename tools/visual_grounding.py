"""Deterministic visual positive/negative controls, unrelated to private video."""

import json
from pathlib import Path
import time
from PIL import Image, ImageDraw, ImageFont
from jsonschema import validate


def verify(model, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    colors = {
        "red": (210, 40, 40),
        "blue": (30, 70, 210),
        "green": (30, 170, 70),
        "yellow": (225, 205, 40),
    }
    variants = [(17, "red", 0), (83, "blue", 1), (42, "green", 2), (65, "yellow", 1)]
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "number": {"type": "integer", "minimum": 0, "maximum": 99},
            "background": {"type": "string", "enum": list(colors)},
            "stick_figures": {"type": "integer", "minimum": 0, "maximum": 2},
        },
        "required": ["number", "background", "stick_figures"],
    }
    counts = {"number_correct": 0, "background_correct": 0, "figure_count_correct": 0}
    for index, (number, color, figures) in enumerate(variants):
        image = Image.new("RGB", (848, 464), colors[color])
        draw = ImageDraw.Draw(image)
        draw.text(
            (424, 10),
            str(number),
            fill="white",
            font=ImageFont.load_default(size=160),
            anchor="mt",
        )
        for i in range(figures):
            x = 320 + i * 180
            draw.ellipse((x - 22, 225, x + 22, 269), fill="black")
            draw.line([(x, 270), (x, 355)], fill="black", width=16)
            draw.line([(x - 48, 320), (x, 285), (x + 48, 320)], fill="black", width=12)
            draw.line([(x - 42, 425), (x, 350), (x + 42, 425)], fill="black", width=14)
        path = directory / f"sample-{index}.png"
        image.save(path)
        image.close()
        raw = model.infer(
            [{"id": "f0000000", "timestamp_sec": 0, "path": str(path)}],
            "Read the large two-digit number, name the dominant background color and count the drawn black stick figures. Use the image only. Return JSON matching "
            + json.dumps(schema),
            time.time() + 60,
            output_schema=schema,
        )
        result = json.loads(raw)
        validate(result, schema)
        (directory / f"synthetic-result-{index}.json").write_text(
            json.dumps(result), encoding="utf-8"
        )
        counts["number_correct"] += result["number"] == number
        counts["background_correct"] += result["background"] == color
        counts["figure_count_correct"] += result["stick_figures"] == figures
    metrics = {
        "synthetic_visual_grounding": True,
        "cases": len(variants),
        **counts,
        "passed_number_color_controls": counts["number_correct"] == len(variants)
        and counts["background_correct"] == len(variants),
        "meaning": "Engineering visual-input sanity check; not bank-event accuracy.",
    }
    (directory / "aggregate.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics), flush=True)
    return metrics
