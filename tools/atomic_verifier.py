"""Experimental independent visual checks; every final legal gate still required."""

import hashlib
import json
from pathlib import Path

from cashproof.inference.pipeline import Observation, WindowOutput
from cashproof.reproducibility import configuration
from fact_pipeline import TriggerFactPipeline


class AtomicFactPipeline(TriggerFactPipeline):
    def __init__(self, model, registry, max_candidates=8):
        super().__init__(model, registry, max_candidates)
        model.runtime_configuration.update(
            experimental_verifier="occurrence-specific independent checks v7; ungrounded opposite cannot clear exclusion; local indices and dense onset refinement",
            atomic_verifier_sha256=hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        )
        self.configuration = configuration(
            max_candidates,
            registry.path,
            getattr(model, "manifest", None),
            model.runtime_configuration,
        )
        self.stage_counts.update(
            atomic_predicate_checks=0,
            atomic_unobservable_checks=0,
            joint_conditions_rejected=0,
            atomic_exclusion_checks=0,
            ungrounded_exclusions_marked_unobservable=0,
        )
        self.uncertainty_spans = []

    def run(self, source, directory, job_id, deadline, progress):
        self.uncertainty_spans = []
        detail, timeline = super().run(source, directory, job_id, deadline, progress)
        for interval in detail["coverage"]:
            if any(
                start <= interval["end_sec"] and end >= interval["start_sec"]
                for start, end in self.uncertainty_spans
            ):
                interval["state"] = "limited"
                interval["reason"] += (
                    " Некоторые условия итоговой проверки не наблюдаемы; отсутствие нарушения не установлено."
                )
        return detail, timeline

    def check(
        self,
        frames,
        statement,
        deadline,
        private_dir,
        focus=None,
        require_counterevidence=False,
    ):
        index = {"type": "integer", "enum": list(range(len(frames)))}
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visible_change": {"type": "string", "maxLength": 120},
                "support": {
                    "type": "string",
                    "enum": ["supported", "contradicted", "unobservable"],
                },
                "first_supported_index": {"anyOf": [index, {"type": "null"}]},
                "evidence_indices": {
                    "type": "array",
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": index,
                },
            },
            "required": [
                "visible_change",
                "support",
                "first_supported_index",
                "evidence_indices",
            ],
        }
        legend = [
            {"index": i, "source_seconds": f["timestamp_sec"]}
            for i, f in enumerate(frames)
        ]
        prompt = (
            "Candidate=independent visual check. Describe the directly visible evidence in ONE short sentence, "
            "then decide whether this ONE statement is supported, contradicted or unobservable. "
            "Supported means visible evidence establishes the statement. Contradicted means visible evidence establishes its opposite. "
            "Use unobservable when evidence is insufficient; missing visibility does not prove absence. "
            "Read images in the supplied order. Do not identify individuals or infer intent, permission or ledger facts. "
            "For supported select its FIRST supportable source index and include it in evidence_indices. "
            "For contradicted/unobservable use null for first_supported_index. "
            "For supported AND contradicted provide actual evidence_indices. An opposite claim without observable evidence is unobservable. "
            + (
                "Proposed occurrence="
                + json.dumps(focus, separators=(",", ":"))
                + ". Assess THIS occurrence. This is an approximate sampled hint, not an exact onset or evidence. "
                "The same continuous action may start in earlier dense frames. Keep separate repeated actions distinct. "
                if focus
                else ""
            )
            + "Statement="
            + statement
            + "\nSource indices="
            + json.dumps(legend, separators=(",", ":"))
            + "\nJSON="
            + json.dumps(schema, separators=(",", ":"))
        )

        def parse(value):
            if (
                require_counterevidence
                and value["support"] == "contradicted"
                and not value["evidence_indices"]
            ):
                # A missing source witness cannot clear an exception. This is
                # uncertain semantics, not a decoder/JSON failure or proof of absence.
                self.stage_counts["ungrounded_exclusions_marked_unobservable"] += 1
                value = dict(value, support="unobservable", first_supported_index=None)
            if value["support"] == "supported" and (
                value["first_supported_index"] is None
                or value["first_supported_index"] not in value["evidence_indices"]
            ):
                raise ValueError(
                    "A supported condition needs linked actual source evidence"
                )
            return value

        value = self._request(frames, prompt, schema, deadline, private_dir, parse)
        self.stage_counts["atomic_unobservable_checks"] += (
            value["support"] == "unobservable"
        )
        if value["support"] == "unobservable" and frames:
            self.uncertainty_spans.append(
                (frames[0]["timestamp_sec"], frames[-1]["timestamp_sec"])
            )
        return value

    def ask(self, frames, verify, deadline, private_dir):
        if not verify:
            return super().ask(frames, verify, deadline, private_dir)
        rule = self.registry.enabled[verify.rule_id]
        focus = self.candidate_focus(frames, verify)
        self.stage_counts["verification_assessments"] += 1
        applicability = self.check(
            frames,
            "The visible activity fits this scope: " + rule["public"]["applicability"],
            deadline,
            private_dir,
            focus,
        )
        if applicability["support"] != "supported":
            return WindowOutput(
                events=[], visibility_limited=applicability["support"] == "unobservable"
            )
        checks = {}
        ordered_keys = sorted(
            rule["predicates"], key=lambda key: key != "customer_absent"
        )
        for key in ordered_keys:
            statement = rule["predicates"][key]
            checks[key] = self.check(frames, statement, deadline, private_dir, focus)
            self.stage_counts["atomic_predicate_checks"] += 1
            if checks[key]["support"] != "supported":
                self.stage_counts["missing_predicates"] += 1
                return WindowOutput(
                    events=[],
                    visibility_limited=checks[key]["support"] == "unobservable",
                )
        context = self.check(
            frames,
            "The relevant boundaries and area are sufficiently visible to establish this event: "
            + json.dumps(rule["predicates"], separators=(",", ":"))
            + ". Context requirement: "
            + rule["context"],
            deadline,
            private_dir,
            focus,
        )
        self.stage_counts["incomplete_context"] += context["support"] != "supported"
        if context["support"] != "supported":
            return WindowOutput(
                events=[], visibility_limited=context["support"] == "unobservable"
            )
        # A disjunction of several exceptions invites an answer about the general
        # action instead of each exception. Preserve the same gate, but establish
        # the opposite of EACH listed exclusion independently.
        for statement in rule["public"]["exclusions"]:
            exclusion = self.check(
                frames,
                "This specific exclusion applies to the proposed occurrence: "
                + statement,
                deadline,
                private_dir,
                focus,
                require_counterevidence=True,
            )
            self.stage_counts["atomic_exclusion_checks"] += 1
            self.stage_counts["exclusions_present"] += (
                exclusion["support"] == "supported"
            )
            if exclusion["support"] != "contradicted":
                return WindowOutput(
                    events=[],
                    visibility_limited=exclusion["support"] == "unobservable",
                )

        index = {"type": "integer", "enum": list(range(len(frames)))}
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visible_change": {"type": "string", "minLength": 1, "maxLength": 120},
                "joint_support": {
                    "type": "string",
                    "enum": ["supported", "contradicted", "unobservable"],
                },
                "event_frame_index": {"anyOf": [index, {"type": "null"}]},
                "evidence_indices": {
                    "type": "array",
                    "minItems": 0,
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": index,
                },
            },
            "required": [
                "visible_change",
                "joint_support",
                "event_frame_index",
                "evidence_indices",
            ],
        }
        prompt = (
            "Candidate="
            + verify.rule_id
            + ". Locate the FIRST supportable instant of the proposed event in these actual source frames. "
            + "Proposed occurrence="
            + json.dumps(focus, separators=(",", ":"))
            + ". This coarse sampled hint may be late. Refine to the FIRST supportable dense frame of the SAME action, "
            "including earlier frames. Keep separate repeated actions distinct. The proposed timestamp is not an onset or proof. "
            "Use the visible action instant, or the instant at which an omitted step first becomes established. "
            "Never select earlier context merely because it is the beginning of the video. "
            "Confirm that ALL conditions are jointly valid for THIS event instant, using before/after context for temporal predicates. "
            "Do not combine unrelated occurrences or conditions that stopped applying before this event. "
            "Earlier independent checks may be mistaken: use contradicted/unobservable joint_support and null event index when joint support is absent. "
            "The event must jointly satisfy all these visually checked conditions: "
            + json.dumps(rule["predicates"], separators=(",", ":"))
            + "\nCondition witnesses (first supportable index and evidence)="
            + json.dumps(
                {
                    k: {
                        "first_supported_index": v["first_supported_index"],
                        "evidence_indices": v["evidence_indices"],
                    }
                    for k, v in checks.items()
                },
                separators=(",", ":"),
            )
            + "\nSource indices="
            + json.dumps(
                [
                    {"index": i, "source_seconds": f["timestamp_sec"]}
                    for i, f in enumerate(frames)
                ],
                separators=(",", ":"),
            )
            + "\nDescribe the visible change in one short sentence. Include the event index in evidence_indices. JSON="
            + json.dumps(schema, separators=(",", ":"))
        )

        def parse(value):
            if value["joint_support"] == "supported" and (
                value["event_frame_index"] is None
                or value["event_frame_index"] not in value["evidence_indices"]
            ):
                raise ValueError("Final event time must be linked to actual evidence")
            return value

        located = self._request(frames, prompt, schema, deadline, private_dir, parse)
        if located["joint_support"] != "supported":
            self.stage_counts["joint_conditions_rejected"] += 1
            limited = located["joint_support"] == "unobservable"
            if limited:
                self.uncertainty_spans.append(
                    (frames[0]["timestamp_sec"], frames[-1]["timestamp_sec"])
                )
            return WindowOutput(events=[], visibility_limited=limited)
        self.stage_counts["eligible_assessments"] += 1
        return WindowOutput(
            events=[
                Observation(
                    rule_id=verify.rule_id,
                    event_frame_id=frames[located["event_frame_index"]]["id"],
                    frame_ids=[frames[i]["id"] for i in located["evidence_indices"]],
                    predicates={key: True for key in checks},
                    applicable=True,
                    complete_context=True,
                    exclusion_present=False,
                    observation=located["visible_change"],
                    counterevidence=[],
                    limitations=[],
                )
            ],
            visibility_limited=False,
        )
