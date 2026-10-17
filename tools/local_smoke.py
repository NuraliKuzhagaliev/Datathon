"""Safe to show aggregate metrics; model outputs are stored only in ignored data."""

import argparse
import json
from pathlib import Path
import time
from cashproof.config import force_offline
from cashproof.inference.model import LocalQwen
from cashproof.media import decode_timeline, extract, sample_indices


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--deny-network", action="store_true")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    force_offline()
    network_attempts = []
    if a.deny_network:
        import socket

        def denied(*args, **kwargs):
            network_attempts.append(True)
            raise OSError("Network access is disabled for the local smoke process")

        socket.socket.connect = denied
        socket.socket.connect_ex = denied
        socket.getaddrinfo = denied
    start = time.perf_counter()
    model = LocalQwen(a.model_dir)
    load = time.perf_counter() - start
    timeline = decode_timeline(a.video, time.time() + 120)
    frames = extract(
        a.video,
        timeline,
        sample_indices(timeline, 0, min(4, timeline.duration), 1),
        a.output / "frames",
        time.time() + 120,
    )
    model.torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    output = model.infer(
        list(frames.values()),
        'Return strict JSON {"readable":true} if the images are readable. Do not identify people.',
        time.time() + 120,
    )
    latency = time.perf_counter() - start
    (a.output / "private-output.txt").write_text(output, encoding="utf-8")
    metrics = {
        "model": model.version,
        "load_sec": load,
        "inference_sec": latency,
        "frames": len(frames),
        "peak_vram_bytes": model.torch.cuda.max_memory_allocated(),
        "gpu": model.torch.cuda.get_device_name(),
        "torch": model.torch.__version__,
        "bf16_supported": model.torch.cuda.is_bf16_supported(),
        "python_network_denied": a.deny_network,
        "network_attempts": len(network_attempts),
    }
    (a.output / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
