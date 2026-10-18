"""Auxiliary source-pixel motion crops; never a violation detector or label reader."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def motion_box(paths):
    if len(paths) < 2:
        return None
    small, geometry = [], None
    for path in paths:
        with Image.open(path) as original:
            if geometry is None:
                geometry = original.size
            if original.size != geometry:
                raise ValueError("Source geometry changed within interval")
            image = original.convert("L")
            image.thumbnail((160, 160))
            small.append(np.asarray(image, dtype=np.float32))
            image.close()
    energy = np.abs(np.diff(np.stack(small), axis=0)).sum(axis=0)
    total = float(energy.sum())
    if total < 1:
        return None
    height, width = energy.shape
    crop_w, crop_h = max(1, round(width * 0.6)), max(1, round(height * 0.6))
    integral = np.pad(energy, ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)
    scores = (
        integral[crop_h:, crop_w:]
        - integral[:-crop_h, crop_w:]
        - integral[crop_h:, :-crop_w]
        + integral[:-crop_h, :-crop_w]
    )
    y, x = np.unravel_index(int(np.argmax(scores)), scores.shape)
    if float(scores[y, x]) / total < 0.5:
        return None  # Diffuse/global movement supplies no justified local crop.
    source_w, source_h = geometry
    return (
        round(x * source_w / width),
        round(y * source_h / height),
        min(source_w, round((x + crop_w) * source_w / width)),
        min(source_h, round((y + crop_h) * source_h / height)),
    )


def pairs(frames, directory):
    if len(frames) > 8:
        raise ValueError("Full+crop pairing would exceed16 images")
    box = motion_box([frame["path"] for frame in frames])
    if box is None:
        return [dict(frame, view_kind="full") for frame in frames], None
    directory.mkdir(parents=True, exist_ok=False)
    output = []
    for i, frame in enumerate(frames):
        output.append(dict(frame, view_kind="full"))
        with Image.open(frame["path"]) as source:
            crop = source.crop(box)
            path = (directory / f"crop-{i}.png").resolve()
            crop.save(path)
            crop.close()
        output.append(
            dict(
                frame,
                id="crop-" + frame["id"],
                source_frame_id=frame["id"],
                path=str(path),
                view_kind="auxiliary_crop",
                source_crop_box=list(box),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return output, list(box)


def prepare(source, output):
    manifest = json.loads(source.read_text(encoding="utf-8"))
    if manifest.get("development_only") is not True:
        raise ValueError("Development diagnostic only")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cropped = 0
    for clip in manifest["clips"]:
        frames, box = pairs(clip["frames"]["fps2-131k"], output / clip["id"])
        clip["frames"] = {"fps2-motion": frames}
        clip["motion_crop_box"] = box
        cropped += box is not None
    manifest.update(
        diagnostic_id=output.name,
        settings={"fps2-motion": {"fps": 2, "pixels": 131072, "image_tokens": 256}},
        auxiliary_motion_views=True,
        source_diagnostic_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        motion_views_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "prepared_motion_diagnostic": True,
                "clips": len(manifest["clips"]),
                "clips_with_localized_motion_crop": cropped,
                "max_images": max(
                    len(clip["frames"]["fps2-motion"]) for clip in manifest["clips"]
                ),
                "labels_used_by_crop_algorithm": False,
                "automatic_violation_accuracy": None,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.output)
