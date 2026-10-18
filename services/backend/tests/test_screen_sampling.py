"""Changing the recorded density must change actual rotated/VFR source inputs."""

import time
from types import SimpleNamespace

import pytest

from cashproof import media
from cashproof.inference.pipeline import Pipeline, ScreenOutput


class RecordingScreen(Pipeline):
    def ask(self, frames, verify, deadline, private_dir):
        assert verify is None
        self.sampled.update(f["index"] for f in frames)
        assert len(frames) <= 16
        return ScreenOutput(events=[], visibility_limited=False)


@pytest.mark.parametrize("fps", [1, 2, 4])
def test_configured_density_changes_actual_source_frames(clip, tmp_path, registry, fps):
    model = SimpleNamespace(
        runtime_configuration={
            "screening_sample_fps": fps,
            "screening_window_sec": 3.5,
            "screening_overlap_sec": 0.5,
        }
    )
    pipeline = RecordingScreen(model, registry)
    pipeline.sampled = set()
    output = tmp_path / "job"
    output.mkdir()
    _, timeline = pipeline.run(
        clip, output, "0" * 32, time.time() + 30, lambda **kw: None
    )
    assert pipeline.sampled == set(media.sample_indices(timeline, fps=fps))
    assert len(pipeline.sampled) >= 4 * fps


@pytest.mark.parametrize("fps", [0, -1, float("nan"), float("inf")])
def test_invalid_density_cannot_hang_source_sampling(fps):
    timeline = media.Timeline([0, 0.5, 1], 0, 1.5, 100, 100)
    with pytest.raises(ValueError):
        media.sample_indices(timeline, fps=fps)
