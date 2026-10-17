from PIL import Image, ImageDraw
import numpy as np
import pytest

from motion_views import motion_box, pairs


def moving_frames(tmp_path):
    frames = []
    for i, x in enumerate((110, 125, 140)):
        image = Image.new("RGB", (300, 200), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 70, 190), fill="black")  # Large static distractor.
        draw.rectangle((x, 120, x + 15, 135), fill="red")
        path = tmp_path / f"generated-{i}.png"
        image.save(path)
        frames.append(
            {"id": f"f{100 + i * 50}", "timestamp_sec": i * 0.5, "path": str(path)}
        )
    return frames


def test_crop_comes_from_pixel_changes_and_retains_exact_source_pixels(tmp_path):
    frames = moving_frames(tmp_path)
    result, box = pairs(frames, tmp_path / "crops")
    assert (
        box is not None
        and box[0] <= 110
        and box[2] >= 155
        and box[1] <= 120
        and box[3] >= 135
    )
    assert len(result) == 6
    for i, frame in enumerate(frames):
        assert result[2 * i + 1]["timestamp_sec"] == frame["timestamp_sec"]
        assert result[2 * i + 1]["source_frame_id"] == frame["id"]
        with (
            Image.open(frame["path"]) as source,
            Image.open(result[2 * i + 1]["path"]) as crop,
        ):
            assert np.array_equal(np.asarray(source.crop(tuple(box))), np.asarray(crop))


def test_static_sequence_does_not_invent_motion_crop(tmp_path):
    frames = moving_frames(tmp_path)
    assert motion_box([frames[0]["path"]] * 3) is None


def test_pairing_never_silently_truncates_image_budget(tmp_path):
    with pytest.raises(ValueError):
        pairs(moving_frames(tmp_path) * 3, tmp_path / "over-budget")
