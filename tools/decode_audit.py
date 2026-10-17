"""Full local decode audit; stdout contains only aggregate technical metadata."""

import argparse
import json
from pathlib import Path
import statistics
import time
from cashproof.media import decode_timeline


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    rows = json.loads(a.manifest.read_text(encoding="utf-8"))["rows"]
    items = []
    seen = set()
    for row in rows:
        if row["sha256"] in seen:
            continue
        seen.add(row["sha256"])
        start = time.time()
        try:
            timeline = decode_timeline(Path(row["path"]), time.time() + 120)
            item = dict(
                sha256=row["sha256"],
                duration_sec=timeline.duration,
                width=timeline.width,
                height=timeline.height,
                frames=len(timeline.pts),
                decode_sec=time.time() - start,
                variable_timing=len(
                    {round(b - a, 5) for a, b in zip(timeline.pts, timeline.pts[1:])}
                )
                > 1,
                ok=True,
            )
        except Exception:
            item = dict(sha256=row["sha256"], ok=False)
        items.append(item)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(items, indent=2), encoding="utf-8")
    good = [i for i in items if i["ok"]]
    print(
        json.dumps(
            dict(
                unique_videos=len(items),
                decoded=len(good),
                failed=len(items) - len(good),
                maximum_duration_sec=max(
                    (i["duration_sec"] for i in good), default=None
                ),
                maximum_decode_sec=max((i["decode_sec"] for i in good), default=None),
                median_decode_sec=statistics.median(i["decode_sec"] for i in good)
                if good
                else None,
                variable_timing_videos=sum(i["variable_timing"] for i in good),
            )
        )
    )


if __name__ == "__main__":
    main()
