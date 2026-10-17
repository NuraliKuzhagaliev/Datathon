import json
import shutil
import time
from PIL import Image
import pytest
from cashproof import media
from cashproof.contracts import validate_result
from cashproof.errors import ProcessingError
from cashproof.inference.pipeline import Pipeline, windows


class ScriptedSyntheticModel:
    def __init__(self, positive=True, invalid=False, excluded=False):
        self.positive, self.invalid, self.excluded = positive, invalid, excluded
        self.calls = 0

    def infer(self, frames, prompt, deadline):
        self.calls += 1
        ids = [f["id"] for f in frames]
        events = []
        if self.positive:
            rules = ["TEST-A", "TEST-B"]
            if "Candidate=" in prompt:
                candidate = json.loads(prompt.split("Candidate=")[1])
                rules = [candidate["rule_id"]]
            for rule in rules:
                frame = ids[min(len(ids) - 1, 2 if rule == "TEST-B" else 0)]
                events.append(
                    dict(
                        rule_id=rule,
                        event_frame_id=frame,
                        frame_ids=["invented"] if self.invalid else [frame],
                        predicates={"observed": True},
                        applicable=True,
                        complete_context=True,
                        exclusion_present=self.excluded,
                        observation="Synthetic test pattern.",
                        counterevidence=[],
                        limitations=[],
                    )
                )
        return json.dumps(dict(events=events, visibility_limited=False))


def test_pts_vfr_rotation_evidence_and_preview(clip, tmp_path):
    timeline = media.decode_timeline(clip, time.time() + 30)
    assert timeline.pts[0] == 0
    assert len({round(b - a, 4) for a, b in zip(timeline.pts, timeline.pts[1:])}) > 1
    frames = media.extract(
        clip,
        timeline,
        media.sample_indices(timeline),
        tmp_path / "frames",
        time.time() + 30,
    )
    for frame in frames.values():
        assert frame["timestamp_sec"] == timeline.pts[frame["index"]]
        with Image.open(frame["path"]) as image:
            assert image.width > image.height  # MOV display rotation was applied
    mapping = media.preview(clip, tmp_path / "preview.mp4", timeline, time.time() + 30)
    assert mapping[0]["source_start_sec"] == mapping[0]["preview_start_sec"] == 0
    actual = media.decode_timeline(tmp_path / "preview.mp4", time.time() + 30)
    assert len(actual.pts) == len(timeline.pts)
    assert max(abs(a - b) for a, b in zip(actual.pts, timeline.pts)) < 0.002


def test_multiple_events_and_renamed_input_invariance(clip, tmp_path, registry):
    model = ScriptedSyntheticModel()
    pipeline = Pipeline(model, registry)
    results = []
    renamed = tmp_path / "renamed.mov"
    shutil.copyfile(clip, renamed)
    for i, source in enumerate([clip, renamed]):
        directory = tmp_path / f"job{i}"
        directory.mkdir()
        detail, timeline = pipeline.run(
            source, directory, "a" * 32, time.time() + 60, lambda **kw: None
        )
        validate_result(detail["model_result"], timeline.duration)
        assert len(detail["events"]) == 2
        assert [e["jury_violation_index"] for e in detail["events"]] == [0, 1]
        results.append(detail["model_result"])
    assert results[0] == results[1]


@pytest.mark.parametrize("positive,excluded", [(False, False), (True, True)])
def test_negative_and_benign_exclusion(clip, tmp_path, registry, positive, excluded):
    detail, _ = Pipeline(
        ScriptedSyntheticModel(positive, excluded=excluded), registry
    ).run(clip, tmp_path, "a" * 32, time.time() + 60, lambda **kw: None)
    assert detail["model_result"]["verdict"] == "no_violation"
    assert detail["model_result"]["violations"] == []


def test_invented_frames_fail_after_one_repair(clip, tmp_path, registry):
    model = ScriptedSyntheticModel(invalid=True)
    with pytest.raises(ProcessingError, match="MODEL_OUTPUT_INVALID"):
        Pipeline(model, registry).run(
            clip, tmp_path, "a" * 32, time.time() + 60, lambda **kw: None
        )
    assert model.calls == 2


def test_full_window_coverage():
    for duration in [1, 28, 28.5, 142.533, 300]:
        plan = list(windows(duration))
        assert plan[0][0] == 0 and plan[-1][1] == duration
        assert all(b[0] <= a[1] for a, b in zip(plan, plan[1:]))


def test_corrupt_and_deadline(tmp_path):
    p = tmp_path / "broken.mov"
    p.write_bytes(b"not video")
    with pytest.raises(ProcessingError):
        media.decode_timeline(p, time.time() + 30)
