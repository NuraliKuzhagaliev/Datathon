"""Synthetic-only visual-input experiment. No label or pixel detector inputs."""
import base64
import io
import json

import av
from PIL import Image, ImageDraw

from gemini_synthetic_smoke import SafeStop

PROMPT = """Inspect these chronological frames of one synthetic animation.
Each image has CONTEXT on the left and a FIXED ZOOM of the SAME frame on the
right. The zoom is a fixed crop of the camera view, NOT an event candidate.
The blue square may be outside the zoom; then use CONTEXT. Compare blue and red
WITHIN ONE panel, never across panels. Source frame IDs and timestamps are given.

Report ALL crossings of the BLUE SQUARE'S CENTER through the RED vertical line,
including both directions. The square's front edge touching the line is NOT a
center crossing. When they overlap, compare blue width on either side of red:
more blue on LEFT means the CENTER is LEFT; more on RIGHT means CENTER is RIGHT.
Only equal widths put the center ON the line. Being near the line is not ON.
Use the enlarged view for small offsets, especially in the FIRST frames.

For each crossing, select a definite before frame and its side, a center-crossing
frame, and a definite after frame and its side. Select the crossing frame whose
center is closest to the red line. If no sampled frame is exactly centered, choose
the first frame on the new side. Use nearby witnesses at most 1.5 seconds apart.
left then right means left_to_right; right then left means right_to_left.
An initial ON state followed by right is insufficient unless a prior LEFT frame
is actually visible. A square can overlap red and remain on the SAME side: no
crossing. Waiting, stopping, touching and returning to the same side are not
events. A continuous one-way pass is ONE crossing, not a crossing at every frame.
Repeated crossings are separate. No crossings means an empty crossings array.

Return only the requested JSON with crossings and a short observation for each.
Use ONLY supplied frame IDs. Do not guess timestamps or infer real-world events.
"""

SCHEMA = {"type": "OBJECT", "properties": {"crossings": {
    "type": "ARRAY", "maxItems": 20, "items": {"type": "OBJECT", "properties": {
        "before_frame_id": {"type": "STRING"},
        "before_side": {"type": "STRING", "enum": ["left", "right"]},
        "event_frame_id": {"type": "STRING"},
        "after_frame_id": {"type": "STRING"},
        "after_side": {"type": "STRING", "enum": ["left", "right"]},
        "direction": {"type": "STRING", "enum": ["left_to_right", "right_to_left"]},
        "observation": {"type": "STRING"}},
        "required": ["before_frame_id", "before_side", "event_frame_id",
                     "after_frame_id", "after_side", "direction", "observation"]}}},
    "required": ["crossings"]}


def visual_input(path):
    parts, frames, target = [], [], 0.0

    def add(frame):
        pts = float(frame.pts * frame.time_base)
        frame_id = f"f{len(frames):04d}"
        with frame.to_image() as original:
            if original.size != (640, 360):
                raise SafeStop("SYNTHETIC_CAMERA_LAYOUT_UNSUPPORTED")
            # Fixed camera crop: no object/line localization or event search.
            with original.crop((240, 100, 400, 300)) as crop:
                with crop.resize((640, 800), Image.Resampling.NEAREST) as zoom:
                    with Image.new("RGB", (1280, 820), "white") as canvas:
                        canvas.paste(original, (0, 210))
                        canvas.paste(zoom, (640, 20))
                        draw = ImageDraw.Draw(canvas)
                        draw.text((12, 5), "CONTEXT", fill="black")
                        draw.text((652, 5), "FIXED ZOOM - SAME FRAME", fill="black")
                        data = io.BytesIO()
                        canvas.save(data, format="JPEG", quality=95)
        parts.extend([{"text": f"Frame {frame_id}; source timestamp {pts:.3f} seconds."},
                      {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(data.getvalue()).decode()}}])
        frames.append({"frame_id": frame_id, "timestamp_sec": pts})

    last = None
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            last = frame
            pts = float(frame.pts * frame.time_base)
            if pts + 1e-8 < target:
                continue
            target += 0.5
            add(frame)
        if last is not None and float(last.pts * last.time_base) > frames[-1]["timestamp_sec"]:
            add(last)
    if not frames or len(frames) > 24:
        raise SafeStop("INVALID_SYNTHETIC_FRAME_COUNT")
    return parts, frames


def parse_witnesses(body, frames):
    try:
        candidate = body["candidates"][0]
        if candidate.get("finishReason") != "STOP":
            raise ValueError()
        value = json.loads("".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought")))
        rows = value["crossings"]
        if not isinstance(rows, list) or len(rows) > 20:
            raise ValueError()
        by_id = {f["frame_id"]: f["timestamp_sec"] for f in frames}
        crossings = []
        for row in rows:
            before, event, after = (by_id[row[k]] for k in ("before_frame_id", "event_frame_id", "after_frame_id"))
            direction = row["direction"]
            expected_sides = {"left_to_right": ("left", "right"), "right_to_left": ("right", "left")}[direction]
            if ((row["before_side"], row["after_side"]) != expected_sides
                    or not before < event <= after or after - before > 1.5
                    or not isinstance(row["observation"], str) or len(row["observation"]) > 1000):
                raise ValueError()
            crossings.append({**row, "before_time_sec": before, "time_sec": event, "after_time_sec": after})
        crossings.sort(key=lambda c: c["time_sec"])
        if len({c["time_sec"] for c in crossings}) != len(crossings):
            raise ValueError()
        return {"crossings": crossings, "event_times_sec": [c["time_sec"] for c in crossings if c["direction"] == "left_to_right"],
                "direction_summary": "Model-selected crossing and witness frame IDs mapped to actual source PTS; no pixel corrections."}
    except (KeyError, ValueError, TypeError, IndexError):
        raise SafeStop("INVALID_MODEL_WITNESSES_OR_SOURCE_IDS") from None
