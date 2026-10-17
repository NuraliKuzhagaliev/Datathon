"""Record the exact implementation used by a case, without private inputs."""

import hashlib
import json
from pathlib import Path
from . import __version__


def configuration(
    max_candidates, registry_path=None, model_manifest=None, runtime_overrides=None
):
    root = Path(__file__).resolve().parent
    sources = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.py"))
    }
    value = {
        "backend_version": __version__,
        "rule_registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest()
        if registry_path
        else None,
        "model_manifest": model_manifest,
        "implementation_sha256": sources,
        "max_candidates": max_candidates,
        "screening_window_sec": 14,
        "screening_overlap_sec": 2,
        "screening_sample_fps": 1,
        "verification_context_radius_sec": 12,
        "verification_dense_radius_sec": 2,
        "verification_dense_fps": 2,
        "screening_max_pixels": 65536,
        "verification_max_pixels": 131072,
        "max_images_per_call": 16,
        "image_max_edge": 448,
        "max_input_tokens": 14000,
        "screening_max_new_tokens": 768,
        "verification_max_new_tokens": 1024,
        "attention": "sdpa",
        "sampling": False,
        "bounded_repairs": 1,
        "json_grammar": "lm-format-enforcer==0.11.3",
    }
    value.update(runtime_overrides or {})
    value["configuration_sha256"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value
