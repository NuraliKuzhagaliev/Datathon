"""Resumable bounded-range public artifact download with mandatory final SHA-256.

Used only for provisioning public binaries/weights. Not imported by the service.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import requests


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--partial", type=Path, required=True)
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    if not a.url.startswith("https://") or not 1 <= a.workers <= 16:
        raise ValueError("Invalid download configuration")
    a.partial.parent.mkdir(parents=True, exist_ok=True)
    offset = a.partial.stat().st_size if a.partial.exists() else 0
    if offset > a.size:
        raise ValueError("Partial artifact exceeds expected size")
    chunk = 8 * 1024 * 1024

    def fetch(start):
        end = min(start + chunk, a.size) - 1
        part = a.partial.with_name(a.partial.name + f".range-{start}")
        for attempt in range(4):
            try:
                with requests.get(
                    a.url,
                    headers={"Range": f"bytes={start}-{end}"},
                    stream=True,
                    timeout=(30, 45),
                ) as response:
                    if (
                        response.status_code != 206
                        or response.headers.get("Content-Range")
                        != f"bytes {start}-{end}/{a.size}"
                    ):
                        raise ValueError("Range response did not match requested bytes")
                    with part.open("wb") as out:
                        for data in response.iter_content(256 * 1024):
                            out.write(data)
                if part.stat().st_size != end - start + 1:
                    raise ValueError("Incomplete range")
                return part
            except Exception:
                part.unlink(missing_ok=True)
                if attempt == 3:
                    raise RuntimeError(
                        "Public artifact range failed after bounded retries"
                    ) from None
                time.sleep(1 + attempt)

    starts = iter(range(offset, a.size, chunk))
    with (
        ThreadPoolExecutor(max_workers=a.workers) as pool,
        a.partial.open("ab") as target,
    ):
        pending = []
        for _ in range(a.workers):
            start = next(starts, None)
            if start is not None:
                pending.append(pool.submit(fetch, start))
        last_report = offset
        while pending:
            future = pending.pop(0)
            part = future.result()
            with part.open("rb") as stream:
                for data in iter(lambda: stream.read(1024 * 1024), b""):
                    target.write(data)
            target.flush()
            part.unlink()
            if target.tell() - last_report >= 64 * 1024 * 1024:
                last_report = target.tell()
                print(
                    json.dumps(
                        {"downloaded_bytes": last_report, "total_bytes": a.size}
                    ),
                    flush=True,
                )
            start = next(starts, None)
            if start is not None:
                pending.append(pool.submit(fetch, start))
    h = hashlib.sha256()
    with a.partial.open("rb") as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(data)
    if a.partial.stat().st_size != a.size or h.hexdigest() != a.sha256:
        raise ValueError("Artifact SHA-256 or size mismatch")
    a.partial.replace(a.destination)
    print(json.dumps({"verified": True, "bytes": a.size, "sha256": h.hexdigest()}))


if __name__ == "__main__":
    main()
