"""Opt-in Gemini free-tier experiment. Generates its own inputs; no dataset access.

Not imported by the production service. No paid fallback, retries, tools or uploads
to persistent file storage. Billing tier must be checked in AI Studio immediately
before use; the Gemini generation endpoint has no free-only request parameter.
"""

import argparse
import base64
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import time

import av
import httpx
import numpy as np
from PIL import Image, ImageDraw

from synthetic_geometry import GeometryUnclear, refine_ambiguous


REPO = Path(__file__).resolve().parents[1]
API = "https://generativelanguage.googleapis.com/v1beta"
# Free input/output tiers verified against Google's pricing on 2026-10-18.
FREE_MODELS = ("gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite")
SCENARIOS = (
    "near_line_start",
    "forward",
    "reverse",
    "repeated",
    "early",
    "late",
    "near_miss",
    "stationary_overlap",
)
PROMPT = """Analyze only the supplied synthetic animation. A blue square moves
relative to a vertical red line. Report EVERY instant when the CENTER of the blue
square crosses that line from LEFT to RIGHT. Right-to-left movement is not an event.
Use seconds from the beginning of this video. Empty list means no qualifying event.
Do not use the square's leading edge. Do not infer any real-world or legal violation.
Return JSON with event_times_sec (array of numbers) and direction_summary (string).
"""
SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "event_times_sec": {"type": "ARRAY", "items": {"type": "NUMBER"}},
        "direction_summary": {"type": "STRING"},
    },
    "required": ["event_times_sec", "direction_summary"],
}
PROMPT_V2 = """Inspect the attached synthetic animation in chronological order.
The fixed red vertical line divides the displayed image into LEFT and RIGHT.
Track the CENTER of the BLUE square, not its leading edge or its overlap with red.

For EACH actual crossing of the center, record three short visual observations:
1. A timestamp immediately BEFORE the crossing and the center's side of the line.
2. The timestamp when the center passes the line, in seconds from video start.
3. A timestamp immediately AFTER the crossing and the center's side of the line.
Use nearby observations (within one second total), not just the video's endpoints.
Timestamps must come from the video timeline; the first displayed frame is 0 s.
Do not shift the clock or round an event to the nearest half-second. A square
touching/overlapping the line without its center changing sides is NOT a crossing.
Waiting or stopping on one side is NOT a crossing. Repeated crossings are separate.

Include BOTH directions in crossings. Determine direction from the two observations:
before=left AND after=right means left_to_right;
before=right AND after=left means right_to_left.
Never infer direction from the requested event type. Inspect the actual movement.

Then event_times_sec must contain ONLY the crossing times whose observed transition
is left_to_right, in chronological order. A video can have crossings and an EMPTY
event_times_sec if all crossings are right_to_left. Keep right_to_left crossings in
the observations but exclude their times from event_times_sec. If nothing crosses,
both arrays are empty. Report what is visible; do not invent missing crossings.
No real-world/legal conclusions. Return the requested JSON, with brief observations.
"""
SCHEMA_V2 = {
    "type": "OBJECT",
    "properties": {
        **SCHEMA["properties"],
        "crossings": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "before_time_sec": {"type": "NUMBER"},
                    "before_side": {"type": "STRING", "enum": ["left", "right"]},
                    "time_sec": {"type": "NUMBER"},
                    "after_time_sec": {"type": "NUMBER"},
                    "after_side": {"type": "STRING", "enum": ["left", "right"]},
                    "direction": {
                        "type": "STRING",
                        "enum": ["left_to_right", "right_to_left"],
                    },
                },
                "required": [
                    "before_time_sec",
                    "before_side",
                    "time_sec",
                    "after_time_sec",
                    "after_side",
                    "direction",
                ],
            },
        },
    },
    "required": [*SCHEMA["required"], "crossings"],
}
PROMPT_V3 = """These are chronological, unmodified frames decoded from ONE
synthetic video. Each frame is preceded by its source frame ID and actual timestamp.
For EACH image independently, locate the CENTER of the blue square and compare it
with the red vertical line in that SAME image. Left/right refer to the displayed
image, not the object's travel direction. Output 'left' if the square's CENTER is
left of the line, 'right' if right, or 'on' if centered on the line (within a few
pixels). A square's edge overlapping the line does not mean its center is on it.
Do not guess future motion or copy the previous image's answer. Output exactly
one side for each supplied frame, in the exact image order. Do not skip duplicates
or stationary frames. Do not report event times: software maps these observations
to the actual source timeline and determines direction from observed side changes.
Return JSON with frame_sides only. No legal or real-world conclusions.
"""
PROMPT_V4 = (
    PROMPT_V3.replace(
        "or 'on' if centered on the line (within a few\npixels).",
        "or 'on' ONLY if the square's exact horizontal MIDPOINT coincides with the line.\nBeing close to the line is NOT 'on'.",
    )
    + """For a square that overlaps the line, compare how much of its horizontal width is
on each side of red. More blue width on the LEFT means its CENTER is LEFT; more
blue width on the RIGHT means its CENTER is RIGHT. Equal widths mean ON.
Equivalently, locate the square's left and right edges, take their midpoint,
and compare that midpoint with the red line. A line inside the square but offset
from its midpoint does NOT place the center on the line. Apply this to stationary
frames as carefully as to moving frames. Do not label a whole near-line interval ON.
"""
)


def ordered_frames(path, *, detail_crop=False):
    """Sample only the generated file; labels are actual decoded PTS, not guesses."""
    parts, frames, next_target = [], [], 0.0
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            pts = float(frame.pts * frame.time_base)
            if pts + 1e-8 < next_target:
                continue
            next_target += 0.25
            frame_id = f"f{len(frames):04d}"
            pixels = frame.to_ndarray(format="rgb24")
            blue = (
                (pixels[:, :, 2] > 150)
                & (pixels[:, :, 0] < 90)
                & (pixels[:, :, 1] < 90)
            )
            xs = np.where(blue)[1]
            if not len(xs):
                raise SafeStop("GENERATED_BLUE_OBJECT_MISSING")
            center = float(xs.mean())
            expected_side = (
                "on"
                if abs(center - 320) <= 3
                else ("left" if center < 320 else "right")
            )
            image = frame.to_image()
            encoded = io.BytesIO()
            image.save(encoded, format="JPEG", quality=95)
            detail = None
            if detail_crop:
                detail_image = image.crop((240, 80, 400, 320))
                detail = io.BytesIO()
                detail_image.save(detail, format="JPEG", quality=95)
                detail_image.close()
            image.close()
            parts.extend(
                [
                    {"text": f"Frame {frame_id}; source timestamp {pts:.3f} seconds."},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": base64.b64encode(encoded.getvalue()).decode(),
                        }
                    },
                ]
            )
            if detail is not None:
                parts.extend(
                    [
                        {
                            "text": f"Detail of SAME source frame {frame_id}, same timestamp. Exact source pixels x=240..400,y=80..320; no resizing or mirroring. Use full view if blue is outside this crop."
                        },
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": base64.b64encode(detail.getvalue()).decode(),
                            }
                        },
                    ]
                )
            # Ground truth is for scoring only; never added to media_parts or prompt.
            frames.append(
                {
                    "frame_id": frame_id,
                    "timestamp_sec": pts,
                    "synthetic_expected_side": expected_side,
                }
            )
    if not frames or len(frames) > 48:
        raise SafeStop("INVALID_GENERATED_FRAME_COUNT")
    return parts, frames


def events_from_sides(value, frames):
    sides = value.get("frame_sides")
    if (
        not isinstance(sides, list)
        or len(sides) != len(frames)
        or any(s not in ("left", "right", "on") for s in sides)
    ):
        raise SafeStop("INVALID_FRAME_OBSERVATIONS")
    previous, contact, crossings = None, None, []
    for index, side in enumerate(sides):
        if side == "on":
            if previous is not None and contact is None:
                contact = index
            continue
        if previous is not None and sides[previous] != side:
            witness = contact if contact is not None else index
            crossings.append(
                {
                    "before_time_sec": frames[previous]["timestamp_sec"],
                    "before_side": sides[previous],
                    "time_sec": frames[witness]["timestamp_sec"],
                    "after_time_sec": frames[index]["timestamp_sec"],
                    "after_side": side,
                    "direction": "left_to_right"
                    if side == "right"
                    else "right_to_left",
                    "event_frame_id": frames[witness]["frame_id"],
                }
            )
        previous, contact = index, None
    return {
        "frame_sides": sides,
        "crossings": crossings,
        "event_times_sec": [
            c["time_sec"] for c in crossings if c["direction"] == "left_to_right"
        ],
        "direction_summary": "Computed from model's per-frame observations and actual source PTS.",
    }


class SafeStop(Exception):
    """Fixed public error messages only, never provider bodies or credentials."""


def load_key(path):
    values = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("GEMINI_API_KEY="):
            values.append(line.strip().split("=", 1)[1].strip().strip("\"'"))
    if len(values) != 1 or not values[0] or "ВАШ_КЛЮЧ" in values[0]:
        raise SafeStop("KEY_MISSING_OR_AMBIGUOUS")
    return values[0]


def verify_free_tier(receipt, key, now=None):
    stamp = datetime.fromisoformat(receipt["checked_at_utc"])
    now = now or datetime.now(timezone.utc)
    age = (now - stamp).total_seconds()
    if (
        receipt.get("billing_tier") != "Free tier"
        or receipt.get("key_sha256") != hashlib.sha256(key.encode()).hexdigest()
        or not receipt.get("verified_in_google_ai_studio")
        or not 0 <= age <= 1800
        or receipt.get("max_spend_usd") != 0
    ):
        raise SafeStop("ZERO_COST_PRECONDITION_NOT_VERIFIED")


def api_json(client, method, route, key, payload=None):
    try:
        response = client.request(
            method,
            API + route,
            headers={"x-goog-api-key": key},
            json=payload,
        )
    except httpx.HTTPError as exc:
        raise SafeStop(f"NETWORK_{type(exc).__name__}_NO_RETRY") from None
    if response.status_code != 200:
        raise SafeStop(f"GEMINI_HTTP_{response.status_code}_NO_RETRY_OR_PAID_FALLBACK")
    try:
        return response.json()
    except ValueError:
        raise SafeStop("INVALID_PROVIDER_JSON") from None


def generate_clip(path, scenario):
    """Public geometric animation, H.264, 10 fps, no audio; exact center truth."""
    duration = 10 if scenario == "repeated" else 6
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width, stream.height, stream.pix_fmt = 640, 360, "yuv420p"
        for i in range(duration * 10):
            t = i / 10
            if scenario == "repeated":
                x = (
                    120 + 100 * t
                    if t <= 4
                    else (520 - 200 * (t - 4) if t <= 6 else 120 + 100 * (t - 6))
                )
            else:
                x = 120 + 100 * max(0, min(4, t - 1))
                if scenario == "reverse":
                    x = 640 - x
                elif scenario == "early":
                    x = 220 + 100 * min(3, t)
                elif scenario == "late":
                    x = 120 + 100 * max(0, t - 3)
                elif scenario == "near_miss":
                    x = 120 + 40 * min(4, t)
                elif scenario == "stationary_overlap":
                    x = 310
                elif scenario == "near_line_start":
                    x = 310 + 20 * max(0, min(2, t - 1))
            image = Image.new("RGB", (640, 360), "white")
            draw = ImageDraw.Draw(image)
            draw.text(
                (15, 15), "SYNTHETIC GEOMETRY TEST - NO REAL FOOTAGE", fill="black"
            )
            draw.line((320, 50, 320, 330), fill="red", width=4)
            draw.rectangle((x - 20, 165, x + 20, 205), fill="blue")
            frame = av.VideoFrame.from_image(image)
            frame.pts, frame.time_base = i, Fraction(1, 10)
            for packet in stream.encode(frame):
                container.mux(packet)
            image.close()
        for packet in stream.encode():
            container.mux(packet)
    return {
        "forward": [3.0],
        "reverse": [],
        "repeated": [2.0, 8.0],
        "early": [1.0],
        "late": [5.0],
        "near_miss": [],
        "stationary_overlap": [],
        "near_line_start": [1.5],
    }[scenario], duration


def validate_result(body, duration, *, witnesses=False, frames=None):
    candidates = body.get("candidates", [])
    if not candidates or candidates[0].get("finishReason") != "STOP":
        raise SafeStop("RESPONSE_BLOCKED_OR_INCOMPLETE")
    text = "".join(
        p.get("text", "")
        for p in candidates[0].get("content", {}).get("parts", [])
        if not p.get("thought", False)
    )
    try:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError()
        if frames is not None:
            return events_from_sides(value, frames)
        times = value["event_times_sec"]
        if (
            not isinstance(times, list)
            or len(times) > 20
            or not isinstance(value["direction_summary"], str)
            or any(
                type(t) not in (int, float)
                or not math.isfinite(t)
                or not 0 <= t < duration
                for t in times
            )
            or times != sorted(set(times))
        ):
            raise ValueError()
        if witnesses:
            validate_crossings(value, duration)
        return value
    except (ValueError, KeyError, TypeError):
        raise SafeStop("INVALID_EVENT_SCHEMA_OR_TIMESTAMPS") from None


def validate_crossings(value, duration):
    """Consistency gate, not an independent check that observations are true."""
    crossings = value.get("crossings")
    if not isinstance(crossings, list) or len(crossings) > 20:
        raise ValueError()
    selected, observed_times = [], []
    for crossing in crossings:
        before, event, after = (
            crossing[k] for k in ("before_time_sec", "time_sec", "after_time_sec")
        )
        if any(
            type(t) not in (int, float) or not math.isfinite(t)
            for t in (before, event, after)
        ):
            raise ValueError()
        if not 0 <= before < event < after < duration or after - before > 1.001:
            raise ValueError()
        transition = (crossing["before_side"], crossing["after_side"])
        direction = {
            ("left", "right"): "left_to_right",
            ("right", "left"): "right_to_left",
        }.get(transition)
        if not direction or crossing["direction"] != direction:
            raise ValueError()
        observed_times.append(event)
        if direction == "left_to_right":
            selected.append(event)
    if (
        observed_times != sorted(set(observed_times))
        or value["event_times_sec"] != selected
    ):
        raise ValueError()


def run(args):
    if args.model not in FREE_MODELS:
        raise SafeStop("MODEL_NOT_IN_FREE_ALLOWLIST")
    if args.refine_geometry and not args.prompt.startswith("frame-sides-"):
        raise SafeStop("GEOMETRY_REQUIRES_SOURCE_FRAMES")
    key = load_key(REPO / ".env.gemini.local")
    receipt = json.loads(args.free_tier_receipt.read_text(encoding="utf-8-sig"))
    verify_free_tier(receipt, key)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "synthetic_only": True,
        "private_videos_sent": 0,
        "max_spend_usd": 0,
        "billing_tier_verified": "Free tier",
        "paid_fallback_enabled": False,
        "automatic_retries": 0,
        "video_fps_requested": 4,
        "cases": [],
        "complete": False,
        "prompt_version": args.prompt,
        "suite": args.suite,
        "generation_requests_started": 0,
        "thinking_budget": args.thinking_budget,
        "source_detail_crop": args.detail_crop,
        "synthetic_pixel_refinement": args.refine_geometry,
        "input_mode": "ordered_source_frames"
        if args.prompt.startswith("frame-sides-")
        else "native_video",
        "meaning": "API/video/direction/source-time sanity test; not bank violation accuracy.",
    }
    try:
        previous_request_start = None
        with httpx.Client(
            timeout=90, follow_redirects=False, trust_env=False
        ) as client:
            models = api_json(client, "GET", "/models?pageSize=1000", key)
            available = {
                m["name"].removeprefix("models/")
                for m in models.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            }
            model = args.model if args.model in available else None
            if model is None:
                raise SafeStop("NO_DOCUMENTED_FREE_VIDEO_MODEL_AVAILABLE")
            report["model_requested"] = model
            scenarios = ["forward", "reverse", "repeated"]
            if args.suite == "extended":
                scenarios = [
                    "near_line_start",
                    *scenarios,
                    "early",
                    "late",
                    "near_miss",
                    "stationary_overlap",
                ]
            elif args.suite == "challenge":
                scenarios = ["early", "late", "near_miss", "stationary_overlap"]
            elif args.suite == "boundary":
                scenarios = ["near_line_start"]
            if args.scenarios:
                scenarios = list(args.scenarios)
                if len(set(scenarios)) != len(scenarios):
                    raise SafeStop("DUPLICATE_SCENARIOS")
            prompt, schema = (
                (PROMPT, SCHEMA)
                if args.prompt == "baseline"
                else (PROMPT_V2, SCHEMA_V2)
            )
            if args.prompt.startswith("frame-sides-"):
                prompt = PROMPT_V4 if args.prompt == "frame-sides-v4" else PROMPT_V3
                if args.detail_crop:
                    prompt = prompt.replace(
                        "For EACH image independently",
                        "For EACH source frame independently",
                    )
                    prompt += "\nEach frame ID has a full image and a same-time detail crop. They are TWO VIEWS of ONE frame, not different times. Output ONE side per source frame ID, not one per image. The crop preserves left/right orientation and original pixels. Use the detail to distinguish the square's midpoint from its edge; use the full image when blue is outside the detail.\n"
            (args.output / "prompt.txt").write_text(prompt, encoding="utf-8")
            report["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
            report["planned_cases"] = len(scenarios)
            for scenario in scenarios:
                verify_free_tier(receipt, key)
                path = args.output / f"synthetic-{scenario}.mp4"
                expected, duration = generate_clip(path, scenario)
                # No arbitrary source-file argument: only bytes just generated here.
                video = path.read_bytes()
                frames = None
                media_parts = [
                    {
                        "inlineData": {
                            "mimeType": "video/mp4",
                            "data": base64.b64encode(video).decode(),
                        },
                        "videoMetadata": {"fps": 4},
                    },
                ]
                if args.prompt.startswith("frame-sides-"):
                    media_parts, frames = ordered_frames(
                        path, detail_crop=args.detail_crop
                    )
                    schema = {
                        "type": "OBJECT",
                        "properties": {
                            "frame_sides": {
                                "type": "ARRAY",
                                "minItems": len(frames),
                                "maxItems": len(frames),
                                "items": {
                                    "type": "STRING",
                                    "enum": ["left", "on", "right"],
                                },
                            },
                        },
                        "required": ["frame_sides"],
                    }
                    (args.output / f"synthetic-{scenario}-frames.json").write_text(
                        json.dumps(frames, indent=2), encoding="utf-8"
                    )
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [*media_parts, {"text": prompt}],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0,
                        "maxOutputTokens": 4096,
                        "responseMimeType": "application/json",
                        "responseSchema": schema,
                        "thinkingConfig": {"thinkingBudget": args.thinking_budget},
                    },
                }
                report["generation_requests_started"] += 1
                report["active_scenario"] = scenario
                if previous_request_start is not None:
                    time.sleep(max(0, 13 - (time.monotonic() - previous_request_start)))
                verify_free_tier(receipt, key)
                started = time.monotonic()
                previous_request_start = started
                body = api_json(
                    client, "POST", f"/models/{model}:generateContent", key, payload
                )
                elapsed = round(time.monotonic() - started, 3)
                (args.output / f"synthetic-{scenario}-response.json").write_text(
                    json.dumps(body, indent=2), encoding="utf-8"
                )
                result = validate_result(
                    body, duration, witnesses=args.prompt != "baseline", frames=frames
                )
                model_result = result
                geometry_observations = []
                if args.refine_geometry:
                    if frames is None:
                        raise SafeStop("GEOMETRY_REQUIRES_SOURCE_FRAMES")
                    try:
                        sides, geometry_observations = refine_ambiguous(
                            path, frames, result["frame_sides"]
                        )
                    except GeometryUnclear:
                        raise SafeStop("SYNTHETIC_GEOMETRY_UNCLEAR") from None
                    result = events_from_sides({"frame_sides": sides}, frames)
                predicted = result["event_times_sec"]
                errors = [round(abs(a - b), 3) for a, b in zip(predicted, expected)]
                all_expected = [(t, "left_to_right") for t in expected]
                if scenario == "reverse":
                    all_expected = [(3.0, "right_to_left")]
                elif scenario == "repeated":
                    all_expected = [
                        (2.0, "left_to_right"),
                        (5.0, "right_to_left"),
                        (8.0, "left_to_right"),
                    ]
                witness_correct = None
                if args.prompt != "baseline":
                    crossings = result["crossings"]
                    witness_correct = len(crossings) == len(all_expected) and all(
                        abs(c["time_sec"] - t) <= 0.5 and c["direction"] == direction
                        for c, (t, direction) in zip(crossings, all_expected)
                    )
                row = {
                    "scenario": scenario,
                    "expected_event_times_sec": expected,
                    "predicted": result,
                    "raw_gemini_result": model_result,
                    "geometry_observations": geometry_observations,
                    "latency_sec": elapsed,
                    "absolute_errors_sec": errors,
                    "passed_within_0_5_sec": len(predicted) == len(expected)
                    and all(e <= 0.5 for e in errors),
                    "all_crossing_directions_and_times_correct": witness_correct,
                    "model_version": body.get("modelVersion"),
                    "usage_metadata": body.get("usageMetadata", {}),
                    "synthetic_video_sha256": hashlib.sha256(video).hexdigest(),
                }
                if frames is not None:
                    row["frame_observations_correct"] = sum(
                        side == f["synthetic_expected_side"]
                        for side, f in zip(result["frame_sides"], frames)
                    )
                    row["frame_observations_total"] = len(frames)
                report["cases"].append(row)
                report.pop("active_scenario", None)
                print(
                    json.dumps(
                        {
                            "scenario": scenario,
                            "expected_event_times_sec": expected,
                            "raw_gemini_event_times_sec": model_result[
                                "event_times_sec"
                            ],
                            "final_event_times_sec": predicted,
                            "latency_sec": elapsed,
                            "passed": row["passed_within_0_5_sec"]
                            and witness_correct is not False,
                            "geometry_frames_reviewed": len(geometry_observations),
                        }
                    ),
                    flush=True,
                )
            report["complete"] = True
            report["passed"] = all(
                r["passed_within_0_5_sec"]
                and r["all_crossing_directions_and_times_correct"] is not False
                for r in report["cases"]
            )
    except SafeStop as exc:
        report["stopped_reason"] = str(exc)
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (args.output / "aggregate.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}), flush=True)
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--free-tier-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=FREE_MODELS, default="gemini-2.5-flash")
    parser.add_argument(
        "--prompt",
        choices=(
            "baseline",
            "direction-witness-v2",
            "frame-sides-v3",
            "frame-sides-v4",
        ),
        default="frame-sides-v3",
    )
    parser.add_argument(
        "--suite",
        choices=("original", "extended", "challenge", "boundary"),
        default="original",
    )
    parser.add_argument(
        "--thinking-budget", type=int, choices=(0, 512, 1024), default=1024
    )
    parser.add_argument("--detail-crop", action="store_true")
    parser.add_argument(
        "--scenarios",
        choices=SCENARIOS,
        nargs="+",
        help="Explicit subset for continuing after free quota reset; does not alter inference.",
    )
    parser.add_argument(
        "--refine-geometry",
        action="store_true",
        help="Explicit synthetic blue/red pixel-geometry experiment; not pure Gemini accuracy.",
    )
    try:
        raise SystemExit(run(parser.parse_args()))
    except SafeStop as exc:
        print(json.dumps({"stopped_reason": str(exc), "inference_started": False}))
        raise SystemExit(1) from None
