import numpy as np
import pytest
from PIL import Image, ImageDraw

from synthetic_geometry import GeometryUnclear, measure_side, refine_ambiguous
from gemini_synthetic_smoke import generate_clip, ordered_frames, events_from_sides


@pytest.mark.parametrize(
    "line_x,center,side",
    [
        (150, 140, "left"),
        (150, 160, "right"),
        (420, 420, "on"),
        (420, 410, "left"),
        (420, 430, "right"),
    ],
)
def test_geometry_follows_observed_line_position(line_x, center, side):
    image = Image.new("RGB", (600, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.line((line_x, 20, line_x, 330), fill="red", width=3)
    draw.rectangle((center - 20, 160, center + 20, 200), fill="blue")
    assert measure_side(np.asarray(image))["side"] == side


def test_no_reference_is_an_error_not_an_invented_side():
    with pytest.raises(GeometryUnclear):
        measure_side(np.full((100, 100, 3), 255, dtype=np.uint8))


def test_two_separated_objects_are_ambiguous():
    image = Image.new("RGB", (600, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.line((300, 20, 300, 330), fill="red", width=3)
    draw.rectangle((100, 160, 140, 200), fill="blue")
    draw.rectangle((400, 160, 440, 200), fill="blue")
    with pytest.raises(GeometryUnclear):
        measure_side(np.asarray(image))


def test_boundary_recovery_uses_pixels_without_scoring_labels(tmp_path):
    path = tmp_path / "synthetic.mp4"
    generate_clip(path, "near_line_start")
    _, frames = ordered_frames(path)
    # Strip scoring labels, so refinement cannot obtain its answers from them.
    source = [{k: f[k] for k in ("frame_id", "timestamp_sec")} for f in frames]
    model_sides = ["on"] * 10 + ["right"] * 14
    refined, observations = refine_ambiguous(path, source, model_sides)
    assert observations[0]["offset_pixels"] < -2
    assert events_from_sides({"frame_sides": refined}, source)["event_times_sec"] == [
        1.5
    ]


def test_initial_on_then_right_never_defaults_to_left():
    source = [{"frame_id": f"f{i}", "timestamp_sec": i / 4} for i in range(3)]
    assert (
        events_from_sides({"frame_sides": ["on", "on", "right"]}, source)[
            "event_times_sec"
        ]
        == []
    )
