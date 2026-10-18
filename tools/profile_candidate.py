"""Synthetic-only timing of local model preparation, prefill and token decoding."""

import argparse
import json
from pathlib import Path
import statistics
import time

from PIL import Image

from candidate_model import CandidateModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    model = CandidateModel(args.model_dir, compact=True, native_video=True)
    loading = time.perf_counter() - started
    torch = model.torch
    image = args.output / "generated-blue.png"
    Image.new("RGB", (320, 160), "blue").save(image)
    frames = [{"id": "f0000000", "timestamp_sec": 0.0, "path": str(image)}]
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"blue": {"type": "boolean"}},
        "required": ["blue"],
    }
    steps = []
    active = []

    def before(module, positional, kwargs):
        event = torch.cuda.Event(enable_timing=True)
        event.record()
        active.append((event, time.perf_counter()))

    def after(module, positional, kwargs, output):
        event = torch.cuda.Event(enable_timing=True)
        event.record()
        begin, wall_start = active.pop()
        steps.append((begin, event, time.perf_counter() - wall_start))

    handles = [
        model.model.register_forward_pre_hook(before, with_kwargs=True),
        model.model.register_forward_hook(after, with_kwargs=True),
    ]
    calls = []
    try:
        for _ in range(2):
            steps.clear()
            torch.cuda.synchronize()
            started = time.perf_counter()
            raw = model.infer(
                frames,
                "Is the dominant background blue? Return the blue boolean in strict JSON.",
                time.time() + 60,
                output_schema=schema,
            )
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
            gpu_times = [begin.elapsed_time(end) / 1000 for begin, end, _ in steps]
            calls.append(
                {
                    "total_sec": elapsed,
                    "forward_steps": len(steps),
                    "prefill_gpu_sec": gpu_times[0] if gpu_times else None,
                    "decode_gpu_sec": sum(gpu_times[1:]),
                    "forward_wall_sec": sum(wall for _, _, wall in steps),
                    "median_decode_gpu_sec": statistics.median(gpu_times[1:])
                    if len(gpu_times) > 1
                    else None,
                    "synthetic_boolean_correct": json.loads(raw) == {"blue": True},
                    "inference_telemetry": model.technical_calls[-1],
                }
            )
    finally:
        for handle in handles:
            handle.remove()
    result = {
        "synthetic_only": True,
        "private_footage_used": False,
        "model_version": model.version,
        "loading_sec": loading,
        "calls": calls,
        "cuda_event_interpretation": (
            "Stream elapsed intervals include host launch gaps; these are not summed kernel times."
        ),
        "meaning": "Engineering latency diagnosis only; no bank-event quality claim",
    }
    (args.output / "aggregate.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
