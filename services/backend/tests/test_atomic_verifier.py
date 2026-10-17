import json
import time

import pytest

from atomic_verifier import AtomicFactPipeline
from cashproof.inference.pipeline import ScreenCandidate
from cashproof.errors import ProcessingError


class ScriptedChecks:
    def __init__(self, statuses):
        self.statuses = ["supported", "supported", "supported", "contradicted"]
        self.statuses[: len(statuses)] = statuses

    def infer(self, frames, instruction, deadline, output_schema=None):
        if "support" not in output_schema["properties"]:
            return json.dumps(
                {
                    "visible_change": "Generated event",
                    "joint_support": "supported",
                    "event_frame_index": 2,
                    "evidence_indices": [2],
                }
            )
        check = (
            1
            if "Statement=The visible activity fits this scope:" in instruction
            else 2
            if "Statement=The relevant boundaries and area" in instruction
            else 3
            if "Statement=This specific exclusion applies" in instruction
            else 0
        )
        status = self.statuses[check]
        return json.dumps(
            {
                "visible_change": "Generated test evidence",
                "support": status,
                "first_supported_index": 2 if status == "supported" else None,
                "evidence_indices": [2] if status != "unobservable" else [],
            }
        )


def test_distinct_occurrences_are_distinguishable_to_every_visual_check(
    registry, tmp_path
):
    prompts = []
    frames = [{"id": f"f{i}", "timestamp_sec": t} for i, t in enumerate([0, 0.4, 2.7])]
    for number, candidate_id in enumerate(["f0", "f2"]):

        class RecordingChecks(ScriptedChecks):
            def infer(self, frames, instruction, deadline, output_schema=None):
                prompts[-1].append(instruction)
                return super().infer(frames, instruction, deadline, output_schema)

        model = RecordingChecks(["supported", "supported", "supported", "contradicted"])
        prompts.append([])
        candidate = ScreenCandidate(
            rule_id="TEST-A",
            event_frame_id=candidate_id,
            frame_ids=[candidate_id],
            predicates={"observed": True},
            applicable=True,
        )
        AtomicFactPipeline(model, registry).ask(
            frames, candidate, time.time() + 60, tmp_path / f"private-{number}"
        )
    assert len(prompts[0]) == len(prompts[1]) == 5
    assert all(a != b for a, b in zip(prompts[0], prompts[1]))


def test_missing_proposed_source_frame_is_a_technical_error(registry, tmp_path):
    model = ScriptedChecks(["supported", "supported", "supported", "contradicted"])
    candidate = ScreenCandidate(
        rule_id="TEST-A",
        event_frame_id="invented",
        frame_ids=["invented"],
        predicates={"observed": True},
        applicable=True,
    )
    with pytest.raises(ProcessingError) as failure:
        AtomicFactPipeline(model, registry).ask(
            [{"id": "f0", "timestamp_sec": 0}],
            candidate,
            time.time() + 60,
            tmp_path / "private",
        )
    assert failure.value.code == "ANALYSIS_INCOMPLETE"


@pytest.mark.parametrize("joint_support", ["contradicted", "unobservable"])
def test_individual_witnesses_do_not_force_a_joint_event(
    registry, tmp_path, joint_support
):
    class NonJointChecks(ScriptedChecks):
        def infer(self, frames, instruction, deadline, output_schema=None):
            if "joint_support" in output_schema["properties"]:
                return json.dumps(
                    {
                        "visible_change": "Generated unrelated conditions",
                        "joint_support": joint_support,
                        "event_frame_index": None,
                        "evidence_indices": [],
                    }
                )
            return super().infer(frames, instruction, deadline, output_schema)

    model = NonJointChecks(["supported", "supported", "supported", "contradicted"])
    pipeline = AtomicFactPipeline(model, registry)
    candidate = ScreenCandidate(
        rule_id="TEST-A",
        event_frame_id="f2",
        frame_ids=["f2"],
        predicates={"observed": True},
        applicable=True,
    )
    result = pipeline.ask(
        [{"id": f"f{i}", "timestamp_sec": float(i)} for i in range(3)],
        candidate,
        time.time() + 60,
        tmp_path / "private",
    )
    assert result.events == []
    assert result.visibility_limited is (joint_support == "unobservable")
    assert pipeline.stage_counts["joint_conditions_rejected"] == 1


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


@pytest.mark.parametrize("second_status", ["supported", "unobservable", "contradicted"])
def test_each_exclusion_requires_its_own_counterevidence(
    registry, tmp_path, second_status
):
    rule = registry.enabled["TEST-A"]
    rule["public"]["exclusions"] = [
        "First generated exception",
        "Second generated exception",
    ]
    queries = []

    class MultipleExclusions(ScriptedChecks):
        def infer(self, frames, instruction, deadline, output_schema=None):
            if "This specific exclusion applies" in instruction:
                queries.append(instruction)
                status = (
                    second_status
                    if "Second generated exception" in instruction
                    else "contradicted"
                )
                return json.dumps(
                    {
                        "visible_change": "Generated counterevidence",
                        "support": status,
                        "first_supported_index": 2 if status == "supported" else None,
                        "evidence_indices": [2] if status != "unobservable" else [],
                    }
                )
            return super().infer(frames, instruction, deadline, output_schema)

    pipeline = AtomicFactPipeline(MultipleExclusions([]), registry)
    candidate = ScreenCandidate(
        rule_id="TEST-A",
        event_frame_id="f2",
        frame_ids=["f2"],
        predicates={"observed": True},
        applicable=True,
    )
    output = pipeline.ask(
        [{"id": f"f{i}", "timestamp_sec": float(i)} for i in range(3)],
        candidate,
        time.time() + 60,
        tmp_path / "private",
    )
    assert len(queries) == 2 and queries[0] != queries[1]
    assert pipeline.stage_counts["atomic_exclusion_checks"] == 2
    assert bool(output.events) is (second_status == "contradicted")
    assert output.visibility_limited is (second_status == "unobservable")


def test_opposite_statement_without_frame_evidence_cannot_clear_an_exclusion(
    registry, tmp_path
):
    class UnsupportedOpposite(ScriptedChecks):
        def infer(self, frames, instruction, deadline, output_schema=None):
            value = json.loads(
                super().infer(frames, instruction, deadline, output_schema)
            )
            if "This specific exclusion applies" in instruction:
                value["evidence_indices"] = []
            return json.dumps(value)

    pipeline = AtomicFactPipeline(UnsupportedOpposite([]), registry)
    candidate = ScreenCandidate(
        rule_id="TEST-A",
        event_frame_id="f2",
        frame_ids=["f2"],
        predicates={"observed": True},
        applicable=True,
    )
    result = pipeline.ask(
        [{"id": f"f{i}", "timestamp_sec": float(i)} for i in range(3)],
        candidate,
        time.time() + 60,
        tmp_path / "private",
    )
    assert result.events == [] and result.visibility_limited
    assert pipeline.stage_counts["ungrounded_exclusions_marked_unobservable"] == 1
    assert pipeline.stage_counts["eligible_assessments"] == 0
