"""Local timestamp-oracle visual diagnostics; no jury verdicts or label lookup."""

import argparse
from collections import Counter
import ctypes
import hashlib
import json
import os
from pathlib import Path
import statistics
import threading
import time

from jsonschema import validate

from diagnostic_clips import ACTION_CODES
from gguf_model import GGUFModel


def question(frames):
    index = {"type": "integer", "enum": list(range(len(frames)))}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "visible_sequence": {"type": "string", "maxLength": 240},
            "actions": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "action_code": {"type": "string", "enum": ACTION_CODES},
                        "visible_change": {"type": "string", "maxLength": 160},
                        "first_source_index": index,
                        "evidence_indices": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 3,
                            "uniqueItems": True,
                            "items": index,
                        },
                    },
                    "required": [
                        "action_code",
                        "visible_change",
                        "first_source_index",
                        "evidence_indices",
                    ],
                },
            },
            "visibility_limited": {"type": "boolean"},
        },
        "required": ["visible_sequence", "actions", "visibility_limited"],
    }
    prompt = (
        "Describe only directly visible actions and changes in these ordered source images. "
        "This is visual description, not a legal judgment. Do not assume any violation or expected event. "
        "Do not infer identity, intent, permission, accounting or events outside the images. "
        "Cash_handling means visible handling/counting/sorting of banknotes; object_handover is an actual transfer between people; "
        "walk_away means actual movement away from the work area, not a turn/reach; document_handling means visible work with paper; "
        "bag_handling means visible handling/opening of a bag; storage_transfer means visibly moving objects into/out of a storage place. "
        "Use other_visible_action for another concrete visible change. A still pose alone does not prove an action. "
        "For each distinct action choose its FIRST supportable local source index and include that index in evidence_indices. "
        "Report an empty actions array when none is observable. Mark visibility limitations truthfully. "
        "No annotations or class labels are supplied. JSON="
        + json.dumps(schema, separators=(",", ":"))
    )
    return prompt, schema


class Resources:
    """Sample global device memory and owned process memory; no cloud telemetry."""

    def __init__(self, model):
        self.model = model
        self.stop = threading.Event()
        self.gpu_peak = self.private_peak = self.working_peak = 0
        self.gpu_available = False

    def __enter__(self):
        self.nvml = None
        if os.name == "nt":
            try:
                lib = ctypes.WinDLL("nvml.dll")
                if lib.nvmlInit_v2() != 0:
                    raise OSError()
                device = ctypes.c_void_p()
                if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(device)) != 0:
                    raise OSError()
                self.nvml, self.device = lib, device
            except (OSError, AttributeError):
                self.nvml = None

        def sample():
            class Memory(ctypes.Structure):
                _fields_ = [
                    (name, ctypes.c_ulonglong) for name in ("total", "free", "used")
                ]

            class ProcessMemory(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                    (name, ctypes.c_size_t)
                    for name in (
                        "peak_working",
                        "working",
                        "peak_paged",
                        "paged",
                        "peak_nonpaged",
                        "nonpaged",
                        "pagefile",
                        "peak_pagefile",
                        "private",
                    )
                ]

            while not self.stop.is_set():
                if self.nvml:
                    mem = Memory()
                    if (
                        self.nvml.nvmlDeviceGetMemoryInfo(
                            self.device, ctypes.byref(mem)
                        )
                        == 0
                    ):
                        self.gpu_available = True
                        self.gpu_peak = max(self.gpu_peak, mem.used)
                if os.name == "nt" and hasattr(self.model.process, "_handle"):
                    counters = ProcessMemory()
                    counters.cb = ctypes.sizeof(counters)
                    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
                    get_memory.argtypes = [
                        ctypes.c_void_p,
                        ctypes.POINTER(ProcessMemory),
                        ctypes.c_ulong,
                    ]
                    if get_memory(
                        int(self.model.process._handle),
                        ctypes.byref(counters),
                        counters.cb,
                    ):
                        self.private_peak = max(self.private_peak, counters.private)
                        self.working_peak = max(self.working_peak, counters.working)
                self.stop.wait(0.2)

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=2)
        if self.nvml:
            self.nvml.nvmlShutdown()

    def result(self):
        return {
            "sampled_global_gpu_used_peak_bytes": self.gpu_peak
            if self.gpu_available
            else None,
            "sampled_owned_runtime_private_peak_bytes": self.private_peak or None,
            "sampled_owned_runtime_working_set_peak_bytes": self.working_peak or None,
            "sampling_period_sec": 0.2,
            "limits": "Sampled peaks, not an allocation guarantee; GPU metric includes other host GPU usage. Startup is outside each inference sample.",
        }


def describe(model, frames, deadline, private_output):
    prompt, schema = question(frames)
    started = time.perf_counter()
    with Resources(model) as resources:
        raw = model.infer(frames, prompt, deadline, schema)
    private_output.write_text(
        json.dumps({"prompt": prompt, "raw": raw}, ensure_ascii=False), encoding="utf-8"
    )
    result = json.loads(raw)
    validate(result, schema)
    if any(
        action["first_source_index"] not in action["evidence_indices"]
        for action in result["actions"]
    ):
        raise ValueError("Unlinked diagnostic action instant")
    return result, time.perf_counter() - started, resources.result()


def run(args):
    source_blob = (args.diagnostic / "manifest.json").read_bytes()
    diagnostic = json.loads(source_blob)
    if (
        diagnostic.get("development_only") is not True
        or diagnostic.get("oracle_time") is not True
    ):
        raise ValueError("Explicit oracle-time development diagnostic required")
    if any(clip["split"] != "development" for clip in diagnostic["clips"]):
        raise ValueError("Validation cannot enter diagnosis")
    args.output.mkdir(parents=True, exist_ok=False)
    technical = []
    for visual_tokens in (256, 512):
        settings = {
            key: value
            for key, value in diagnostic["settings"].items()
            if value["image_tokens"] == visual_tokens
        }
        if not settings:
            continue
        model = GGUFModel(
            args.model_dir,
            args.runtime,
            args.provision_receipt,
            args.output / f"runtime-{visual_tokens}",
            screen_pixels=131072,
            conversion_receipt=args.conversion_receipt,
            image_max_tokens=visual_tokens,
            context_size=diagnostic["context_tokens"],
        )
        try:
            if not model.verify_grammar(args.output / f"grammar-{visual_tokens}")[
                "passed"
            ]:
                raise RuntimeError("Diagnostic grammar control failed")
            from visual_grounding import verify as visual_verify
            from temporal_grounding import verify as order_verify

            visual = visual_verify(model, args.output / f"visual-{visual_tokens}")
            if (
                not visual["passed_number_color_controls"]
                or visual["figure_count_correct"] != visual["cases"]
                or not order_verify(model, args.output / f"order-{visual_tokens}")[
                    "passed"
                ]
            ):
                raise RuntimeError("Diagnostic visual/order controls failed")
            model.technical_calls.clear()
            model.runtime_configuration["screening_max_new_tokens"] = 1024
            for setting, spec in settings.items():
                model.runtime_configuration["screening_max_pixels"] = spec["pixels"]
                for clip in diagnostic["clips"]:
                    frames = clip["frames"][setting]
                    if not 1 <= len(frames) <= 16:
                        raise ValueError("Invalid prepared frame budget")
                    record = {
                        "setting": setting,
                        "frames": len(frames),
                        "failed": False,
                    }
                    try:
                        result, elapsed, resources = describe(
                            model,
                            frames,
                            time.time() + 90,
                            args.output / f"{clip['id']}-{setting}-private.json",
                        )
                        record.update(
                            elapsed_sec=elapsed,
                            visibility_limited=result["visibility_limited"],
                            action_count=len(result["actions"]),
                            resources=resources,
                        )
                    except Exception as error:
                        record.update(
                            failed=True,
                            error_type=type(error).__name__,
                            error_code=getattr(
                                error, "code", "DIAGNOSTIC_OUTPUT_INVALID"
                            ),
                        )
                    technical.append(record)
                    (args.output / "progress.json").write_text(
                        json.dumps(
                            {
                                "finished": len(technical),
                                "total": len(diagnostic["clips"])
                                * len(diagnostic["settings"]),
                                "failed": sum(x["failed"] for x in technical),
                            }
                        ),
                        encoding="utf-8",
                    )
                    if model.closed:
                        raise RuntimeError(
                            "Owned diagnostic runtime stopped after failure"
                        )
        finally:
            model.close()
    groups = {}
    for setting in diagnostic["settings"]:
        rows = [r for r in technical if r["setting"] == setting]
        done = [r for r in rows if not r["failed"]]
        groups[setting] = {
            "inputs": len(rows),
            "completed": len(done),
            "failed": len(rows) - len(done),
            "clips_with_action_proposals": sum(r["action_count"] > 0 for r in done),
            "limited_clips": sum(r["visibility_limited"] for r in done),
            "latency_median_sec": statistics.median(r["elapsed_sec"] for r in done)
            if done
            else None,
            "latency_max_sec": max((r["elapsed_sec"] for r in done), default=None),
            "failure_codes": dict(
                Counter(r["error_code"] for r in rows if r["failed"])
            ),
            "sampled_gpu_peak_bytes": max(
                (
                    r["resources"]["sampled_global_gpu_used_peak_bytes"] or 0
                    for r in done
                ),
                default=0,
            )
            or None,
            "sampled_runtime_private_peak_bytes": max(
                (
                    r["resources"]["sampled_owned_runtime_private_peak_bytes"] or 0
                    for r in done
                ),
                default=0,
            )
            or None,
        }
    aggregate = {
        "diagnostic_only": True,
        "oracle_time": True,
        "automatic_detection_accuracy": None,
        "action_accuracy": None,
        "human_action_truth_available": False,
        "diagnostic_manifest_sha256": hashlib.sha256(source_blob).hexdigest(),
        "source_commit": args.source_commit,
        "model": args.model_dir.name,
        "settings": groups,
        "validation_inference_performed": False,
        "limits": "Neutral visual proposals on annotation-centred positive snippets and midpoint negatives. Proposal rate is not accuracy. Negative video labels do not imply the absence of every action. Independent human action/time truth is required before scoring.",
    }
    (args.output / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("diagnostic", "model-dir", "runtime", "provision-receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--conversion-receipt", type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    try:
        run(args)
    except Exception as error:
        print(
            json.dumps(
                {
                    "diagnostic_failed": True,
                    "error_type": type(error).__name__,
                    "error_code": getattr(error, "code", None),
                }
            ),
            flush=True,
        )
        raise SystemExit(1)
