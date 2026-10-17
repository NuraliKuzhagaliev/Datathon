import json
import time

import pytest

from atomic_verifier import AtomicFactPipeline
from cashproof.inference.pipeline import ScreenCandidate


class ScriptedChecks:
    def __init__(self, statuses):
        self.responses = [
            {
                "visible_change": "Generated test evidence",
                "support": status,
                "first_supported_index": 2 if status == "supported" else None,
                "evidence_indices": [2] if status == "supported" else [],
            }
            for status in statuses
        ]
        self.responses.append(
            {
                "visible_change": "Generated event",
                "event_frame_index": 2,
                "evidence_indices": [2],
            }
        )

    def infer(self, frames, instruction, deadline, output_schema=None):
        return json.dumps(self.responses.pop(0))


@pytest.mark.parametrize(
    "statuses,accepted",
    [
        (["supported", "supported", "supported", "contradicted"], True),
        (["contradicted"], False),
        (["unobservable"], False),
        (["supported", "contradicted", "supported", "contradicted"], False),
        (["supported", "unobservable", "supported", "contradicted"], False),
        (["supported", "supported", "contradicted", "contradicted"], False),
        (["supported", "supported", "unobservable", "contradicted"], False),
        (["supported", "supported", "supported", "supported"], False),
        (["supported", "supported", "supported", "unobservable"], False),
    ],
)
def test_every_legal_gate_is_required_and_unknown_exclusion_never_passes(
    registry, tmp_path, statuses, accepted
):
    model = ScriptedChecks(statuses)
    pipeline = AtomicFactPipeline(model, registry)
    candidate = ScreenCandidate(
        rule_id="TEST-A",
        event_frame_id="f2",
        frame_ids=["f2"],
        predicates={"observed": True},
        applicable=True,
    )
    result = pipeline.ask(
        [{"id": f"f{i}", "timestamp_sec": t} for i, t in enumerate([0, 0.7, 2.3])],
        candidate,
        time.time() + 60,
        tmp_path / "private",
    )
    assert bool(result.events) == accepted
    if accepted:
        event = result.events[0]
        assert event.event_frame_id == "f2" and event.frame_ids == ["f2"]
        assert (
            event.applicable and event.complete_context and not event.exclusion_present
        )
        assert all(event.predicates.values())
    else:
        assert pipeline.stage_counts["eligible_assessments"] == 0
