"""Qwen video input with explicit original PTS, never frame-index / assumed FPS."""

import math
from types import MethodType


def temporal_patch_times(source_pts, indices, merge_size):
    indices = list(indices)
    if not indices or merge_size < 1 or not all(math.isfinite(t) for t in source_pts):
        raise ValueError("Invalid temporal metadata")
    if any(not 0 <= i < len(source_pts) for i in indices):
        raise ValueError("Temporal index outside source")
    if len(indices) % merge_size:
        indices += [indices[-1]] * (merge_size - len(indices) % merge_size)
    return [
        (source_pts[indices[i]] + source_pts[indices[i + merge_size - 1]]) / 2
        for i in range(0, len(indices), merge_size)
    ]


def native_inputs(processor, frames, images, text, torch, max_pixels):
    import numpy as np

    pts = [float(f["timestamp_sec"]) for f in frames]
    if any(b < a for a, b in zip(pts, pts[1:])):
        raise ValueError("Video frames must be in PTS order")
    # Qwen's video longest_edge is a TOTAL pixel budget, unlike the image
    # processor's per-image max_pixels. Explicit temporal padding keeps the
    # per-frame spatial budget unchanged for odd-length inputs too.
    temporal_factor = int(processor.video_processor.temporal_patch_size)
    pad = (-len(images)) % temporal_factor
    padded_images = images + [images[-1]] * pad
    pts = pts + [pts[-1]] * pad
    tensor = torch.stack(
        [torch.from_numpy(np.array(image)).permute(2, 0, 1) for image in padded_images]
    )
    fps = (
        (len(pts) - 1) / (pts[-1] - pts[0])
        if len(pts) > 1 and pts[-1] > pts[0]
        else 1.0
    )
    original = processor._calculate_timestamps
    processor._calculate_timestamps = MethodType(
        lambda self, indices, video_fps, merge_size: temporal_patch_times(
            pts, indices, merge_size
        ),
        processor,
    )
    try:
        return processor(
            text=[text],
            videos=[tensor],
            return_tensors="pt",
            padding=True,
            videos_kwargs={
                "do_sample_frames": False,
                "video_metadata": [
                    {
                        "total_num_frames": len(pts),
                        "fps": fps,
                        "frames_indices": list(range(len(pts))),
                    }
                ],
                "size": {
                    "shortest_edge": 1024 * len(pts),
                    "longest_edge": max_pixels * len(pts),
                },
            },
        )
    finally:
        processor._calculate_timestamps = original
