"""Provision pinned Windows binaries from a vendor linked by ffmpeg.org."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile
import requests

URL = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--destination", type=Path, required=True)
    a = p.parse_args()
    a.destination.mkdir(parents=True, exist_ok=True)
    response = requests.get(URL + ".sha256", timeout=30)
    response.raise_for_status()
    expected = response.text.strip().split()[0]
    archive = a.destination / "ffmpeg-9.0.2.zip"
    if not archive.exists():
        with requests.get(URL, stream=True, timeout=(30, 60)) as r:
            r.raise_for_status()
            with archive.open("wb") as out:
                for data in r.iter_content(1024 * 1024):
                    out.write(data)
    h = hashlib.sha256()
    with archive.open("rb") as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(data)
    if h.hexdigest() != expected:
        raise ValueError("FFmpeg archive checksum mismatch")
    with ZipFile(archive) as z:
        for item in z.infolist():
            name = Path(item.filename).name
            if name in {
                "ffmpeg.exe",
                "ffprobe.exe",
                "LICENSE",
                "LICENSE.txt",
                "README.txt",
            }:
                with z.open(item) as source, (a.destination / name).open("wb") as out:
                    shutil.copyfileobj(source, out)
    manifest = {
        "version": "9.0.2",
        "source_url": URL,
        "archive_sha256": expected,
        "license": "GPL-3.0-or-later",
        "source_commit_url": "https://github.com/FFmpeg/FFmpeg/commit/946fcce07b",
        "vendor_url": "https://www.gyan.dev/ffmpeg/builds/",
        "redistribution_review_required": True,
    }
    (a.destination / "provenance.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {"provisioned": True, "version": "9.0.2", "archive_sha256": expected}
        )
    )


if __name__ == "__main__":
    main()
