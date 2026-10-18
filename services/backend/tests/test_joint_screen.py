import json
import time

import pytest
from PIL import Image, ImageDraw

from joint_screen import JointScreenPipeline
from cashproof.errors import ProcessingError


class Responses:
    def __init__(self, indices, state="observed", overflow=False):
        self.indices = list(indices)
        self.state = state
        self.overflow = overflow

    def infer(self, frames, instruction, deadline, output_schema=None):
        checks = {
            key: {"state": "absent"}
            for key in output_schema["properties"]["checks"]["required"]
        }
        checks["TEST-A"] = {"state": self.state}
        indices = self.indices.pop(0)
        if self.state == "observed":
            checks["TEST-A"].update(
                visible_change="Generated action",
                event_indices=indices,
                overflow=self.overflow,
            )
        return json.dumps(
            {
                "visible_sequence": "Generated sequence",
                "checks": checks,
                "visibility_limited": False,
            }
        )


def frames(start):
    return [{"id": f"f{i}", "timestamp_sec": float(i)} for i in range(start, start + 4)]


def test_distinct_occurrences_and_overlapping_windows_keep_actual_source_witnesses(
    registry, tmp_path
):
    pipeline = JointScreenPipeline(Responses([[2, 3], [0, 2]]), registry)
    first = pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "a")
    second = pipeline.ask(frames(2), None, time.time() + 60, tmp_path / "b")
    assert [e.event_frame_id for e in first.events] == ["f2", "f3"]
    assert [e.event_frame_id for e in second.events] == ["f2", "f4"]
    # Exact source witnesses allow the core pipeline to merge only the common f2;
    # no inferred episode/context fingerprint may discard f3 or f4.
    assert [e.frame_ids for e in second.events] == [["f2"], ["f4"]]


def test_invalid_source_index_cannot_become_valid_candidate(registry, tmp_path):
    pipeline = JointScreenPipeline(Responses([[999], [999]]), registry)
    with pytest.raises(ProcessingError) as failure:
        pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "a")
    assert failure.value.code == "MODEL_OUTPUT_INVALID"


def test_auxiliary_crop_witness_maps_to_original_source_frame(registry, tmp_path):
    source = []
    for i, x in enumerate((100, 110, 120, 130)):
        with Image.new("RGB", (300, 200), "white") as image:
            ImageDraw.Draw(image).rectangle((x, 80, x + 10, 100), fill="black")
            path = tmp_path / f"generated-{i}.png"
            image.save(path)
        source.append(
            {"id": f"original-{i}", "timestamp_sec": i * 0.5, "path": str(path)}
        )
    pipeline = JointScreenPipeline(Responses([[1]]), registry, use_motion_views=True)
    output = pipeline.ask(source, None, time.time() + 60, tmp_path / "private")
    assert output.events[0].event_frame_id == "original-0"
    assert output.events[0].frame_ids == ["original-0"]


def test_unclear_answer_preserves_limited_coverage(registry, tmp_path):
    pipeline = JointScreenPipeline(Responses([[]], state="unclear"), registry)
    output = pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "private")
    assert not output.events and output.visibility_limited


def test_observed_without_witness_is_invalid(registry, tmp_path):
    pipeline = JointScreenPipeline(Responses([[], []]), registry)
    with pytest.raises(ProcessingError) as failure:
        pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "private")
    assert failure.value.code == "MODEL_OUTPUT_INVALID"


def test_explicit_overflow_is_not_silently_truncated(registry, tmp_path):
    pipeline = JointScreenPipeline(Responses([[1, 2, 3]], overflow=True), registry)
    with pytest.raises(ProcessingError) as failure:
        pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "private")
    assert failure.value.code == "RESOURCE_EXHAUSTED"
