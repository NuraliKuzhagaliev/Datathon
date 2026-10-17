"""End-to-end model/pipeline controls on generated VFR movement videos only."""

from fractions import Fraction
import hashlib
import json
import time

import av
from PIL import Image, ImageDraw

from cashproof.rules import Registry


def create(
    path,
    reverse=False,
    positions=(120, 230, 410, 560),
    pts_ms=(0, 400, 1200, 2700),
    line_x=350,
):
    with av.open(str(path), "w", format="mov") as container:
        stream = container.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 720, 400, "yuv420p"
        stream.time_base = Fraction(1, 1000)
        stream.codec_context.time_base = Fraction(1, 1000)
        positions = list(positions)
        if len(positions) != len(pts_ms):
            raise ValueError("Generated position/PTS length mismatch")
        if reverse:
            positions.reverse()
        for pts, x in zip(pts_ms, positions):
            with Image.new("RGB", (720, 400), "white") as image:
                draw = ImageDraw.Draw(image)
                draw.line((line_x, 20, line_x, 380), fill="red", width=10)
                draw.ellipse((x - 20, 70, x + 20, 110), fill="black")
                draw.line((x, 110, x, 240), fill="black", width=10)
                draw.line((x - 40, 160, x, 130, x + 40, 160), fill="black", width=8)
                draw.line((x - 35, 320, x, 235, x + 35, 320), fill="black", width=8)
                frame = av.VideoFrame.from_image(image)
            frame.pts, frame.time_base = pts, Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def verify(model, directory, pipeline_class, extended=False):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "generated-source.txt"
    source.write_text("Generated geometry test only; no legal force.", encoding="utf-8")
    rule = {
        "public": {
            "rule_id": "TEST-MOVE",
            "display_name": "Generated crossing control only",
            "document_title": "Generated geometry; no legal force",
            "source_url": "https://example.invalid/synthetic",
            "clause": "test",
            "revision": "1",
            "effective_date": "2020-01-01",
            "applicability": "Only the generated black stick figure and stationary red vertical line in this synthetic video.",
            "exclusions": ["Movement from right to left", "No drawn figure visible"],
            "enabled": True,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "predicates": {
            "crossing": "A drawn black stick figure crosses the red vertical line from LEFT to RIGHT during this sequence; right-to-left does not satisfy it. For the proposed occurrence, the event instant is its FIRST source frame with the figure to the right of the line after previously being left of it. Separate crossings are distinct occurrences."
        },
        "context": "The figure is visible on both sides of the stationary red line before and after the movement. This generated geometric rule does not require any bank, cashier, customer or permission.",
        "snapshot": source.name,
        "template": "Generated synthetic control only, no legal force.",
    }
    registry_path = directory / "generated-registry.json"
    registry_path.write_text(
        json.dumps({"version": "synthetic-source-time-1", "rules": [rule]}),
        encoding="utf-8",
    )
    registry = Registry(registry_path)
    rows = []
    variants = [("forward", {}, [1.2]), ("reverse", {"reverse": True}, [])]
    if extended:
        variants.extend(
            [
                (
                    "early",
                    {"positions": (120, 410, 500, 560), "pts_ms": (0, 720, 1440, 3120)},
                    [0.72],
                ),
                (
                    "late",
                    {
                        "positions": (120, 200, 260, 560, 620),
                        "pts_ms": (0, 320, 1040, 2720, 3640),
                    },
                    [2.72],
                ),
                ("no-cross", {"positions": (80, 130, 180, 220)}, []),
                (
                    "repeated",
                    {
                        "positions": (120, 410, 500, 120, 560, 620),
                        "pts_ms": (0, 400, 1200, 2400, 3400, 4400),
                    },
                    [0.4, 3.4],
                ),
            ]
        )
    for number, (name, render_options, expected) in enumerate(variants):
        video = create(directory / (name + ".mov"), **render_options)
        case = directory / (name + "-case")
        case.mkdir()
        started = time.monotonic()
        detail, timeline = pipeline_class(model, registry).run(
            video,
            case,
            format(number + 1, "032x"),
            time.time() + 180,
            lambda **kwargs: None,
        )
        result = detail["model_result"]
        times = [e["timecode_sec"] for e in result["violations"]]
        correct = (
            result["verdict"] == ("violation" if expected else "no_violation")
            and len(times) == len(expected)
            and all(abs(a - b) < 0.04 for a, b in zip(times, expected))
        )
        rows.append(
            {
                "direction": name,
                "passed": correct,
                "event_count": len(times),
                "event_source_times_sec": times,
                "expected_source_time_sec": expected[0] if len(expected) == 1 else None,
                "expected_source_times_sec": expected,
                "decoded_source_pts_sec": timeline.pts,
                "decoded_vfr": len(
                    {round(b - a, 6) for a, b in zip(timeline.pts, timeline.pts[1:])}
                )
                > 1,
                "elapsed_sec": time.monotonic() - started,
            }
        )
    aggregate = {
        "synthetic_only": True,
        "source_time_end_to_end": True,
        "passed": all(r["passed"] and r["decoded_vfr"] for r in rows),
        "cases": rows,
        "meaning": "Generated MOV -> actual decode/sample -> the candidate's real screen and final checks -> source PTS/evidence. Not bank-event accuracy.",
    }
    (directory / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate), flush=True)
    return aggregate
