"""Exercise the actual server without printing verdicts, descriptions or evidence.

Requests/responses are written only under the explicitly private output directory.
The API key is read from an environment variable and never printed.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import time
import uuid
import httpx


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument("--key-env", default="CASHPROOF_API_KEY")
    a = p.parse_args()
    if not 1 <= a.concurrency <= 5:
        raise ValueError("Concurrency must be 1 to 5")
    a.output.mkdir(parents=True, exist_ok=True)
    key = os.environ[a.key_env]

    def run(index):
        start = time.time()
        with httpx.Client(
            base_url=a.base_url, headers={"X-API-Key": key}, timeout=30, trust_env=False
        ) as client:
            with a.video.open("rb") as video:
                response = client.post(
                    "/api/v1/analyze",
                    files={"file": ("benchmark.mov", video, "video/quicktime")},
                )
            if response.status_code != 202:
                return {
                    "admission_http": response.status_code,
                    "elapsed_sec": time.time() - start,
                }
            job = response.json()["job_id"]
            accepted = time.time() - start
            while time.time() - start < 300:
                response = client.get("/api/v1/jobs/" + job)
                response.raise_for_status()
                value = response.json()
                if value["status"] != "processing":
                    (a.output / f"{index}-{job}.json").write_text(
                        json.dumps(value, ensure_ascii=False), encoding="utf-8"
                    )
                    return {
                        "admission_http": 202,
                        "status": value["status"],
                        "error_code": value.get("error", {}).get("code"),
                        "admission_sec": accepted,
                        "elapsed_sec": time.time() - start,
                    }
                time.sleep(0.5)
            return {
                "admission_http": 202,
                "status": "timed_out",
                "elapsed_sec": time.time() - start,
            }

    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        results = list(pool.map(run, range(a.concurrency)))
    latencies = [r["elapsed_sec"] for r in results if r.get("status") == "done"]
    summary = {
        "run_id": uuid.uuid4().hex,
        "submitted": a.concurrency,
        "accepted": sum(r["admission_http"] == 202 for r in results),
        "done": sum(r.get("status") == "done" for r in results),
        "failed": sum(r.get("status") == "failed" for r in results),
        "results": results,
        "completed_latency_median_sec": statistics.median(latencies)
        if latencies
        else None,
        "completed_latency_max_sec": max(latencies) if latencies else None,
        "quality_evaluated": False,
    }
    (a.output / "technical-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
