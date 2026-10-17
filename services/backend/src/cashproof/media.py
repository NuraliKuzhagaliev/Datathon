"""PTS-based decoding; evidence is extracted without overlays or geometric resizing."""

from dataclasses import dataclass
import base64
import hashlib
import math
import os
from pathlib import Path
import re
import subprocess
import time
import av
from .errors import ProcessingError


def ffmpeg():
    configured = os.getenv("CASHPROOF_FFMPEG")
    if configured:
        return configured
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, deadline, *, loglevel="error"):
    remaining = deadline - time.time()
    if remaining <= 0:
        raise ProcessingError("DEADLINE_EXCEEDED", "Deadline exceeded")
    try:
        result = subprocess.run(
            [
                ffmpeg(),
                "-nostdin",
                "-hide_banner",
                "-xerror",
                "-loglevel",
                loglevel,
                *args,
            ],
            capture_output=True,
            timeout=remaining,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        raise ProcessingError("DEADLINE_EXCEEDED", "Deadline exceeded") from None
    if result.returncode:
        # Decoder logs may contain source metadata; never echo them into public logs.
        raise ProcessingError("DECODE_FAILED", "The video could not be decoded")
    return result


def validate_container(path: Path):
    try:
        with av.open(str(path)) as container:
            if "mov" not in container.format.name or len(container.streams.video) != 1:
                raise ValueError()
            stream = container.streams.video[0]
            if (
                stream.codec_context.name != "h264"
                or stream.width * stream.height > 4096 * 2160
            ):
                raise ValueError()
            if stream.width < 16 or stream.height < 16:
                raise ValueError()
    except Exception:
        raise ProcessingError(
            "DECODE_FAILED",
            "Expected a readable MOV/MP4 container with one H.264 video stream",
        ) from None


@dataclass
class Timeline:
    pts: list[float]
    origin: float
    duration: float
    width: int
    height: int

    def nearest(self, sec):
        import bisect

        i = bisect.bisect_left(self.pts, sec)
        return min(
            {max(0, i - 1), min(len(self.pts) - 1, i)},
            key=lambda j: abs(self.pts[j] - sec),
        )


def decode_timeline(path: Path, deadline: float):
    validate_container(path)
    pts, last_duration = [], 0.0
    try:
        with av.open(str(path), options={"err_detect": "explode"}) as container:
            stream = container.streams.video[0]
            width, height = stream.width, stream.height
            for frame in container.decode(stream):
                if time.time() > deadline:
                    raise ProcessingError("DEADLINE_EXCEEDED", "Deadline exceeded")
                if frame.pts is None:
                    raise ValueError()
                sec = float(frame.pts * frame.time_base)
                if not math.isfinite(sec) or (pts and sec < pts[-1]):
                    raise ValueError()
                pts.append(sec)
                last_duration = float((frame.duration or 0) * frame.time_base)
                if len(pts) > 90000:
                    raise ProcessingError(
                        "RESOURCE_EXHAUSTED", "Decode frame budget exceeded"
                    )
            if not pts:
                raise ValueError()
            origin = pts[0]
            relative = [round(p - origin, 9) for p in pts]
            if not last_duration and len(pts) > 1:
                last_duration = pts[-1] - pts[-2]
            duration = relative[-1] + max(last_duration, 0)
            if duration <= 0:
                raise ValueError()
            return Timeline(relative, origin, duration, width, height)
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError(
            "DECODE_FAILED", "The video could not be completely decoded"
        ) from None


def sample_indices(timeline: Timeline, start=0.0, end=None, fps=1.0):
    end = timeline.duration if end is None else min(end, timeline.duration)
    indices, t = set(), start
    while t < end:
        indices.add(timeline.nearest(t))
        t += 1 / fps
    indices.add(timeline.nearest(max(start, end - 0.001)))
    return sorted(indices)


def extract(
    path: Path, timeline: Timeline, indices: list[int], directory: Path, deadline: float
):
    directory.mkdir(parents=True, exist_ok=True)
    indices = sorted(set(indices))
    if not indices or indices[-1] >= len(timeline.pts) or indices[0] < 0:
        raise ValueError("Invalid frame index")
    # select is evaluated before any rate conversion. FFmpeg applies MOV rotation.
    selected = "+".join(f"eq(n\\,{i})" for i in indices)
    result = run(
        [
            "-copyts",
            "-err_detect",
            "explode",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"select={selected},showinfo",
            "-fps_mode",
            "vfr",
            "-q:v",
            "2",
            "-y",
            str(directory / "%06d.jpg"),
        ],
        deadline,
        loglevel="info",
    )
    raw_pts = [
        float(p)
        for p in re.findall(
            rb"\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([-+\d.eE]+)", result.stderr
        )
    ]
    files = sorted(directory.glob("*.jpg"))
    if len(raw_pts) != len(indices) or len(files) != len(indices):
        raise ProcessingError("DECODE_FAILED", "Evidence frame count mismatch")
    frames = {}
    for i, raw, file in zip(indices, raw_pts, files):
        if abs(raw - timeline.origin - timeline.pts[i]) > 0.002:
            raise ProcessingError("DECODE_FAILED", "Source timestamp mapping mismatch")
        frame_id = f"f{i:07d}"
        frames[frame_id] = {
            "id": frame_id,
            "index": i,
            "timestamp_sec": timeline.pts[i],
            "path": str(file),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
    return frames


def evidence(frame):
    return {
        "timestamp_sec": frame["timestamp_sec"],
        "image_base64": base64.b64encode(Path(frame["path"]).read_bytes()).decode(
            "ascii"
        ),
    }


def preview(path: Path, destination: Path, timeline: Timeline, deadline: float):
    tmp = destination.with_name("preview.partial.mp4")
    run(
        [
            "-err_detect",
            "explode",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "setpts=PTS-STARTPTS",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-fps_mode",
            "vfr",
            "-video_track_timescale",
            "90000",
            "-movflags",
            "+faststart",
            "-y",
            str(tmp),
        ],
        deadline,
    )
    mapped = decode_timeline(tmp, deadline)
    if len(mapped.pts) != len(timeline.pts) or any(
        abs(a - b) > 0.002 for a, b in zip(mapped.pts, timeline.pts)
    ):
        tmp.unlink(missing_ok=True)
        raise ProcessingError(
            "DECODE_FAILED", "Preview alignment could not be verified"
        )
    tmp.replace(destination)
    return [
        {
            "source_start_sec": 0,
            "source_end_sec": timeline.duration,
            "preview_start_sec": 0,
            "preview_end_sec": timeline.duration,
        }
    ]
