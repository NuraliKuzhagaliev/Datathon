import json
import time

import pytest
from PIL import Image, ImageDraw

from joint_screen import JointScreenPipeline
from cashproof.errors import ProcessingError


class Responses:
    def __init__(self, events, states=None):
        self.events = list(events)
        self.states = list(states or ["customer_visible"] * len(events))

    def infer(self, frames, instruction, deadline, output_schema=None):
        checks = {
            key: {
                "state": "absent",
            }
            for key in output_schema["properties"]["checks"]["required"]
        }
        events = self.events.pop(0)
        if events:
            checks["TEST-A"] = {
                "state": "observed",
                "visible_change": "Generated test action",
                "events": events,
                "overflow": False,
            }
        return json.dumps(
            {
                "visible_sequence": "Generated sequence",
                "customer_area_state": self.states.pop(0),
                "activity_context": "ongoing_service",
                "worker_area_state": "at_station",
                "checks": checks,
                "visibility_limited": False,
            }
        )


def event(start=0, end=3, continued=False):
    return {
        "onset_index": start,
        "last_active_index": end,
        "continues_from_window_start": continued,
    }


def frames(start):
    return [{"id": f"f{i}", "timestamp_sec": float(i)} for i in range(start, start + 4)]


def test_only_explicit_overlapping_continuation_in_unchanged_visible_context_merges(
    registry, tmp_path
):
    model = Responses(
        [[event()], [event(continued=True)], [event(continued=True)]],
        ["customer_visible", "customer_visible", "fully_visible_empty"],
    )
    pipeline = JointScreenPipeline(model, registry, use_motion_views=False)
    outputs = [
        pipeline.ask(frames(start), None, time.time() + 60, tmp_path / str(start))
        for start in (0, 2, 4)
    ]
    assert [len(output.events) for output in outputs] == [1, 0, 1]
    assert pipeline.stage_counts["merged_visible_continuations"] == 1
    assert outputs[-1].events[0].event_frame_id == "f4"


def test_distinct_new_occurrences_are_not_merged_even_in_overlapping_windows(
    registry, tmp_path
):
    pipeline = JointScreenPipeline(
        Responses([[event()], [event()]]), registry, use_motion_views=False
    )
    assert pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "a").events
    assert pipeline.ask(frames(2), None, time.time() + 60, tmp_path / "b").events


def test_unclear_context_does_not_hide_new_candidates_by_continuation_merge(
    registry, tmp_path
):
    pipeline = JointScreenPipeline(
        Responses([[event()], [event(continued=True)]], ["mixed", "mixed"]),
        registry,
        use_motion_views=False,
    )
    assert pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "a").events
    assert pipeline.ask(frames(2), None, time.time() + 60, tmp_path / "b").events


def test_invented_interval_cannot_select_a_clean_source_time(registry, tmp_path):
    pipeline = JointScreenPipeline(
        Responses([[event(start=2, end=1)], [event(start=2, end=1)]]),
        registry,
        use_motion_views=False,
    )
    with pytest.raises(ProcessingError) as failure:
        pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "a")
    assert failure.value.code == "MODEL_OUTPUT_INVALID"


def test_auxiliary_crop_onset_maps_back_to_original_source_frame(registry, tmp_path):
    source = []
    for i, x in enumerate((100, 110, 120, 130)):
        image = Image.new("RGB", (300, 200), "white")
        ImageDraw.Draw(image).rectangle((x, 80, x + 10, 100), fill="black")
        path = tmp_path / f"generated-{i}.png"
        image.save(path)
        source.append(
            {"id": f"original-{i}", "timestamp_sec": i * 0.5, "path": str(path)}
        )
    pipeline = JointScreenPipeline(
        Responses([[event(start=1, end=7, continued=True)]]),
        registry,
        use_motion_views=True,
    )
    output = pipeline.ask(source, None, time.time() + 60, tmp_path / "private")
    assert output.events[0].event_frame_id == "original-0"
    assert output.events[0].frame_ids == ["original-0"]


def test_compact_unclear_answer_preserves_limited_coverage(registry, tmp_path):
    class Unclear(Responses):
        def infer(self, *args, **kwargs):
            value = json.loads(super().infer(*args, **kwargs))
            value["checks"]["TEST-A"] = {"state": "unclear"}
            return json.dumps(value)

    pipeline = JointScreenPipeline(Unclear([[]]), registry)
    output = pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "private")
    assert not output.events
    assert output.visibility_limited


def test_observed_state_without_source_occurrence_cannot_be_valid(registry, tmp_path):
    class Unsupported(Responses):
        def infer(self, *args, **kwargs):
            value = json.loads(super().infer(*args, **kwargs))
            value["checks"]["TEST-A"] = {
                "state": "observed",
                "visible_change": "Unlinked test",
                "events": [],
                "overflow": False,
            }
            return json.dumps(value)

    pipeline = JointScreenPipeline(Unsupported([[], []]), registry)
    with pytest.raises(ProcessingError) as failure:
        pipeline.ask(frames(0), None, time.time() + 60, tmp_path / "private")
    assert failure.value.code == "MODEL_OUTPUT_INVALID"
