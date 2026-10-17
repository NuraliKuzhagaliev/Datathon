"""Validate the generated VFR control harness through decoding and final evidence."""

import json

import numpy as np
import pytest
from PIL import Image

from fact_pipeline import TriggerFactPipeline
from source_time_controls import verify
from atomic_verifier import AtomicFactPipeline


class GeneratedGeometryOracle:
    """Synthetic fixture only: red line is fixed at x350 and the figure is black."""

    def infer(self, frames, instruction, deadline, output_schema=None):
        positions = []
        for frame in frames:
            with Image.open(frame["path"]) as image:
                pixels = np.asarray(image.convert("RGB"))
            positions.append(float(np.where(pixels.max(axis=2) < 40)[1].mean()))
        onsets = [
            i
            for i in range(1, len(positions))
            if positions[i] > 350 and positions[i - 1] < 350
        ]
        focus = (
            json.JSONDecoder().raw_decode(
                instruction.split("Proposed occurrence=", 1)[1]
            )[0]
            if "Proposed occurrence=" in instruction
            else None
        )
        onset = (
            min(
                onsets,
                key=lambda i: abs(frames[i]["timestamp_sec"] - focus["source_seconds"]),
            )
            if onsets and focus
            else onsets[0]
            if onsets
            else None
        )
        properties = output_schema["properties"]
        if "people_visible" in properties:
            result = {
                "sequence": "Generated geometry only",
                "people_visible": True,
                "visibility_limited": False,
            }
        elif "support" in properties:
            supported = (
                onset is not None
                and "At least ONE of these exclusions" not in instruction
            )
            result = {
                "visible_change": "Generated geometry evidence",
                "support": "supported" if supported else "contradicted",
                "first_supported_index": onset if supported else None,
                "evidence_indices": [onset] if supported else [],
            }
        elif "event_frame_index" in properties and "predicates" not in properties:
            result = {
                "visible_change": "Generated crossing",
                "event_frame_index": onset,
                "evidence_indices": [onset],
            }
        elif "predicates" in properties:
            assert onset is not None  # Reverse video must never reach verification.
            result = {
                "observation": "Generated line crossing.",
                "predicates": {"crossing": True},
                "applicable": True,
                "complete_context": True,
                "exclusion_present": False,
                "event_frame_index": onset,
                "evidence_indices": [onset],
                "counterevidence": [],
                "limitations": [],
            }
        else:
            result = {
                "visible_change": "Generated geometric movement",
                "observed": onset is not None,
                "indices": onsets,
                "visibility_limited": False,
                "overflow": False,
            }
        return json.dumps(result)


@pytest.mark.parametrize(
    "pipeline_class,extended",
    [
        (TriggerFactPipeline, False),
        (AtomicFactPipeline, False),
        (AtomicFactPipeline, True),
    ],
)
def test_vfr_control_runs_all_the_way_to_exact_source_time(
    tmp_path, pipeline_class, extended
):
    result = verify(
        GeneratedGeometryOracle(), tmp_path, pipeline_class, extended=extended
    )
    assert result["passed"]
    assert result["cases"][0]["event_source_times_sec"] == [1.2]
    assert result["cases"][1]["event_source_times_sec"] == []
    assert result["cases"][0]["decoded_source_pts_sec"] == [0.0, 0.4, 1.2, 2.7]
    if extended:
        assert result["cases"][-1]["event_source_times_sec"] == [0.4, 3.4]
