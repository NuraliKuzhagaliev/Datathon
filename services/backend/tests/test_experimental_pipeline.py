import json
import time

import pytest

from cashproof.errors import ProcessingError
from compact_pipeline import CompactPipeline
from native_frames import temporal_patch_times, native_inputs


class SyntheticAssessment:
    def __init__(self, predicate=True, context=True, excluded=False, invalid=False):
        self.predicate, self.context, self.excluded = predicate, context, excluded
        self.invalid = invalid
        self.calls = 0
        self.flag_key = "possible"
        self.negative_screen = False

    def infer(self, frames, prompt, deadline, output_schema=None):
        self.calls += 1
        if not prompt.startswith("Candidate="):
            return json.dumps(
                {
                    "observation": "Synthetic colored pattern.",
                    "checks": {
                        rule: {
                            self.flag_key: not self.negative_screen,
                            "frame_index": 999
                            if self.invalid
                            else min(i, len(frames) - 1),
                        }
                        for i, rule in enumerate(["TEST-A", "TEST-B"])
                    },
                    "visibility_limited": False,
                }
            )
        return json.dumps(
            {
                "observation": "Synthetic pattern, not footage.",
                "predicates": {"observed": self.predicate},
                "applicable": True,
                "complete_context": self.context,
                "exclusion_present": self.excluded,
                "event_frame_index": 0,
                "evidence_indices": [0],
                "counterevidence": ["Synthetic exclusion"] if self.excluded else [],
                "limitations": [] if self.context else ["Synthetic missing context"],
            }
        )


@pytest.mark.parametrize(
    "predicate,context,excluded,expected",
    [
        (True, True, False, 2),
        (False, True, False, 0),
        (True, False, False, 0),
        (True, True, True, 0),
    ],
)
def test_compact_assessment_keeps_final_legal_gates(
    clip, tmp_path, registry, predicate, context, excluded, expected
):
    model = SyntheticAssessment(predicate, context, excluded)
    detail, _ = CompactPipeline(model, registry).run(
        clip, tmp_path, "a" * 32, time.time() + 60, lambda **kwargs: None
    )
    assert len(detail["events"]) == expected
    assert detail["model_result"]["verdict"] == (
        "violation" if expected else "no_violation"
    )
    assert model.calls == 3  # Both proposed categories assessed even when rejected.


def test_compact_rejects_invented_indices_after_one_repair(clip, tmp_path, registry):
    model = SyntheticAssessment(invalid=True)
    with pytest.raises(ProcessingError) as error:
        CompactPipeline(model, registry).run(
            clip, tmp_path, "a" * 32, time.time() + 60, lambda **kwargs: None
        )
    assert error.value.code == "MODEL_OUTPUT_INVALID"
    assert model.calls == 2


def test_observed_wording_maps_only_predefined_source_indices(clip, tmp_path, registry):
    model = SyntheticAssessment()
    model.flag_key = "trigger_observed"
    detail, timeline = CompactPipeline(model, registry, screen_wording="observed").run(
        clip, tmp_path, "a" * 32, time.time() + 60, lambda **kwargs: None
    )
    assert len(detail["events"]) == 2
    assert all(e["timecode_sec"] in timeline.pts for e in detail["events"])


def test_unused_negative_index_cannot_create_an_event(clip, tmp_path, registry):
    model = SyntheticAssessment()
    model.flag_key = "trigger_observed"
    model.negative_screen = True
    detail, _ = CompactPipeline(model, registry, screen_wording="observed").run(
        clip, tmp_path, "a" * 32, time.time() + 60, lambda **kwargs: None
    )
    assert detail["events"] == []
    assert detail["model_result"]["verdict"] == "no_violation"
    assert model.calls == 1


def test_native_temporal_patches_use_actual_source_pts():
    assert temporal_patch_times([11.0, 11.12, 12.7], [0, 1, 2], 2) == pytest.approx(
        [11.06, 12.7]
    )
    with pytest.raises(ValueError):
        temporal_patch_times([0.0, 1.0], [0, 9], 2)


def test_native_video_uses_actual_vfr_pts_and_restores_processor():
    from pathlib import Path
    from PIL import Image
    import torch
    from transformers import AutoProcessor

    root = Path(__file__).resolve().parents[3]
    if not (root / "models/Qwen3-VL-2B-Instruct/config.json").is_file():
        pytest.skip(
            "Optional local processor integration needs provisioned public model assets"
        )
    processor = AutoProcessor.from_pretrained(
        str(root / "models/Qwen3-VL-2B-Instruct"),
        local_files_only=True,
        trust_remote_code=False,
    )
    original = processor._calculate_timestamps
    frames = [
        {"id": f"f{i}", "timestamp_sec": t} for i, t in enumerate([11.0, 11.12, 12.7])
    ]
    images = [Image.new("RGB", (320, 160), color) for color in ["red", "blue", "green"]]
    text = processor.apply_chat_template(
        [
            {
                "role": "user",
                "content": [
                    {"type": "video"},
                    {"type": "text", "text": "Describe synthetic colors."},
                ],
            }
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    try:
        batch = native_inputs(processor, frames, images, text, torch, 65536)
        decoded = processor.tokenizer.decode(batch["input_ids"][0])
        assert "<11.1 seconds>" in decoded and "<12.7 seconds>" in decoded
        assert batch["video_grid_thw"][0, 0].item() == 2
        assert processor._calculate_timestamps == original
        assert batch["pixel_values_videos"].device.type == "cpu"
    finally:
        for image in images:
            image.close()
