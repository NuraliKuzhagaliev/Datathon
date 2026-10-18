"""Pixel geometry for the blue-object/red-line synthetic task ONLY.

No labels, scenario names, expected times or fixed line coordinates are inputs.
Not a bank-event detector and not evidence that a VLM learned pixel geometry.
"""

import av
import numpy as np


class GeometryUnclear(ValueError):
    pass


def measure_side(rgb):
    blue = (rgb[:, :, 2] > 150) & (rgb[:, :, 0] < 90) & (rgb[:, :, 1] < 90)
    red = (rgb[:, :, 0] > 150) & (rgb[:, :, 1] < 90) & (rgb[:, :, 2] < 90)
    by, bx = np.where(blue)
    if len(bx) < 40 or not np.any(red):
        raise GeometryUnclear("SYNTHETIC_REFERENCE_NOT_VISIBLE")
    # Require a single filled rectangle rather than combining unrelated objects.
    width, height = int(bx.max() - bx.min() + 1), int(by.max() - by.min() + 1)
    if len(bx) / (width * height) < 0.9:
        raise GeometryUnclear("SYNTHETIC_OBJECT_AMBIGUOUS")
    columns = red.sum(axis=0)
    support = np.flatnonzero(columns >= max(12, rgb.shape[0] * 0.2))
    if not len(support) or support[-1] - support[0] > 10:
        raise GeometryUnclear("SYNTHETIC_LINE_AMBIGUOUS")
    object_center = (float(bx.min()) + float(bx.max())) / 2
    line_center = float(support.mean())
    delta = object_center - line_center
    return {
        "side": "on" if abs(delta) <= 2 else "left" if delta < 0 else "right",
        "object_center_x": object_center,
        "line_center_x": line_center,
        "offset_pixels": delta,
    }


def refine_ambiguous(path, frames, model_sides):
    if len(frames) != len(model_sides):
        raise GeometryUnclear("FRAME_COUNT_MISMATCH")
    # Review all uncertain observations and their immediate temporal neighbours.
    indices = sorted(
        {
            j
            for i, side in enumerate(model_sides)
            if side == "on"
            for j in (i - 1, i, i + 1)
            if 0 <= j < len(frames)
        }
    )
    needed = {round(frames[i]["timestamp_sec"], 6): i for i in indices}
    sides, observations = list(model_sides), []
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            pts = round(float(frame.pts * frame.time_base), 6)
            if pts not in needed:
                continue
            index = needed.pop(pts)
            observation = measure_side(frame.to_ndarray(format="rgb24"))
            observations.append(
                {
                    "frame_id": frames[index]["frame_id"],
                    "timestamp_sec": pts,
                    "model_side": model_sides[index],
                    **observation,
                }
            )
            sides[index] = observation["side"]
    if needed:
        raise GeometryUnclear("SOURCE_FRAME_NOT_FOUND")
    return sides, observations
