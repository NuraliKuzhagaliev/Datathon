"""Deterministic public test pattern, never sourced from competition footage."""

from pathlib import Path
import argparse
import time
from cashproof.media import run


def create(path: Path, *, rotated=False, vfr=True, duration=4):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("pattern-base.mov") if rotated else path
    filters = "select='not(mod(n,2))+not(mod(n,5))'" if vfr else "null"
    run(
        [
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=240x400:rate=30:duration={duration}",
            "-vf",
            filters,
            "-fps_mode",
            "vfr",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(tmp),
        ],
        time.time() + 30,
    )
    if rotated:
        run(
            [
                "-display_rotation:v:0",
                "90",
                "-i",
                str(tmp),
                "-c",
                "copy",
                "-y",
                str(path),
            ],
            time.time() + 30,
        )
        tmp.unlink()
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    p.add_argument("--rotated", action="store_true")
    a = p.parse_args()
    create(a.path, rotated=a.rotated)
