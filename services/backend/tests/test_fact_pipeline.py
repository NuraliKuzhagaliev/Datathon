import json
import time
import pytest
from fact_pipeline import FactPipeline
from cashproof.errors import ProcessingError


class FactModel:
    def __init__(self, state="observed", indices=None, overflow=False, people=True):
        self.state = state
        self.indices = [2] if indices is None else indices
        self.overflow = overflow
        self.calls = 0
        self.people = people

    def infer(self, frames, prompt, deadline, output_schema=None):
        self.calls += 1
        if "people_visible" in output_schema["properties"]:
            return json.dumps(
                {
                    "sequence": "Generated movement only",
                    "people_visible": self.people,
                    "visibility_limited": False,
                }
            )
        return json.dumps(
            {
                "observed": self.state == "observed",
                "indices": self.indices,
                "visibility_limited": self.state == "unclear",
                "overflow": self.overflow,
            }
        )


@pytest.mark.parametrize(
    "state,indices,count", [("observed", [2], 2), ("absent", [], 0), ("unclear", [], 0)]
)
def test_fact_screen_has_explicit_negatives_and_exact_source_index(
    registry, tmp_path, state, indices, count
):
    model = FactModel(state, indices)
    frames = [{"id": f"f{i}", "timestamp_sec": t} for i, t in enumerate([0, 0.7, 2.3])]
    result = FactPipeline(model, registry).ask(
        frames, None, time.time() + 60, tmp_path / "private"
    )
    assert len(result.events) == count
    assert all(
        e.event_frame_id == "f2" and e.frame_ids == ["f2"] for e in result.events
    )
    assert model.calls == 3


@pytest.mark.parametrize(
    "state,indices",
    [("observed", []), ("observed", [999]), ("absent", [999]), ("unclear", [999])],
)
def test_invented_or_unsupported_instants_fail_after_one_repair(
    registry, tmp_path, state, indices
):
    model = FactModel(state, indices)
    with pytest.raises(ProcessingError) as error:
        FactPipeline(model, registry).ask(
            [{"id": "f0", "timestamp_sec": 0}],
            None,
            time.time() + 60,
            tmp_path / "private",
        )
    assert error.value.code == "MODEL_OUTPUT_INVALID"
    assert model.calls == 3


def test_no_people_inventory_ends_before_action_questions(registry, tmp_path):
    model = FactModel(people=False)
    result = FactPipeline(model, registry).ask(
        [{"id": "f0", "timestamp_sec": 0}], None, time.time() + 60, tmp_path / "private"
    )
    assert result.events == [] and model.calls == 1


@pytest.mark.parametrize("state", ["absent", "unclear"])
def test_bounded_unused_negative_index_cannot_become_evidence(
    registry, tmp_path, state
):
    model = FactModel(state, [0])
    result = FactPipeline(model, registry).ask(
        [{"id": "f0", "timestamp_sec": 0}], None, time.time() + 60, tmp_path / "private"
    )
    assert result.events == []


def test_fact_overflow_is_technical_failure_not_clean_result(registry, tmp_path):
    with pytest.raises(ProcessingError) as error:
        FactPipeline(FactModel("absent", [], True), registry).ask(
            [{"id": "f0", "timestamp_sec": 0}],
            None,
            time.time() + 60,
            tmp_path / "private",
        )
    assert error.value.code == "RESOURCE_EXHAUSTED"
