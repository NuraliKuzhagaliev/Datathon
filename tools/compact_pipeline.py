"""Development-only compact assessment experiment; final legal gates unchanged."""

import hashlib
import json
from pathlib import Path
import uuid

from jsonschema import Draft202012Validator
from cashproof.errors import ProcessingError
from cashproof.inference.pipeline import (
    Pipeline,
    Observation,
    ScreenCandidate,
    ScreenOutput,
    WindowOutput,
)


class CompactPipeline(Pipeline):
    @staticmethod
    def candidate_focus(frames, candidate):
        frame = next((f for f in frames if f["id"] == candidate.event_frame_id), None)
        if frame is None:
            raise ProcessingError(
                "ANALYSIS_INCOMPLETE",
                "Proposed source frame is absent from verification context",
            )
        return {
            "sampled_local_index": next(i for i, f in enumerate(frames) if f is frame),
            "source_seconds": frame["timestamp_sec"],
        }

    def __init__(self, model, registry, max_candidates=8, screen_wording="possible"):
        if screen_wording not in {"possible", "observed"}:
            raise ValueError("Unknown experimental screening wording")
        self.screen_wording = screen_wording
        self.stage_counts = {
            "screening_calls": 0,
            "possible_triggers": 0,
            "verification_assessments": 0,
            "eligible_assessments": 0,
            "incomplete_context": 0,
            "exclusions_present": 0,
            "missing_predicates": 0,
            "evidence_link_normalizations": 0,
        }
        model.runtime_configuration = getattr(model, "runtime_configuration", {}) | {
            "experimental_pipeline": "compact explicit assessments v1",
            "experimental_screen_wording": screen_wording,
            "experimental_pipeline_sha256": hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        }
        super().__init__(model, registry, max_candidates)

    def _request(self, frames, prompt, schema, deadline, private_dir, validate):
        private_dir.mkdir(exist_ok=True)
        validator = Draft202012Validator(schema)
        for attempt in range(2):
            raw = self.model.infer(frames, prompt, deadline, output_schema=schema)
            (private_dir / f"{uuid.uuid4().hex}.json").write_text(
                json.dumps({"prompt": prompt, "output": raw}, ensure_ascii=False),
                encoding="utf-8",
            )
            try:
                value = json.loads(raw)
                validator.validate(value)
                return validate(value)
            except Exception:
                if attempt:
                    raise ProcessingError(
                        "MODEL_OUTPUT_INVALID", "Compact assessment failed validation"
                    ) from None
                prompt += "\nCorrect the JSON, exact rule/predicate keys and supplied frame indices. Return one object."

    def ask(self, frames, verify, deadline, private_dir):
        if not frames:
            raise ProcessingError("ANALYSIS_INCOMPLETE", "No sampled frames")
        frame_index = {"type": "integer", "enum": list(range(len(frames)))}
        legend = [
            {"index": i, "id": f["id"], "source_seconds": round(f["timestamp_sec"], 6)}
            for i, f in enumerate(frames)
        ]
        if not verify:
            flag_key = (
                "trigger_observed" if self.screen_wording == "observed" else "possible"
            )
            check = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    flag_key: {"type": "boolean"},
                    "frame_index": {"anyOf": [frame_index, {"type": "null"}]},
                },
                "required": [flag_key, "frame_index"],
            }
            schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "observation": {"type": "string", "maxLength": 200},
                    "checks": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {key: check for key in self.registry.enabled},
                        "required": list(self.registry.enabled),
                    },
                    "visibility_limited": {"type": "boolean"},
                },
                "required": ["observation", "checks", "visibility_limited"],
            }
            triggers = [
                {
                    "rule_id": key,
                    "action_triggers": {
                        k: rule["predicates"][k]
                        for k in rule.get(
                            "candidate_triggers", list(rule["predicates"])
                        )
                    },
                    "trigger_mode": rule.get("candidate_trigger_mode", "any"),
                }
                for key, rule in self.registry.enabled.items()
            ]
            prompt = (
                "Describe the visible sequence briefly first. Then check each action trigger once. This is an action screen, not a legal verdict. A normal scene or merely a person being present is not an action trigger. possible=true requires a visually supported action/omission candidate; use its frame index. For false use null. Full legal context is assessed later. Never infer identity, intent, authorization or unseen steps.\nActions="
                + json.dumps(triggers, separators=(",", ":"))
                + "\nFrame indices="
                + json.dumps(legend, separators=(",", ":"))
                + "\nReturn JSON="
                + json.dumps(schema, separators=(",", ":"))
            )
            if self.screen_wording == "observed":
                prompt = prompt.replace(
                    "possible=true requires a visually supported action/omission candidate; use its frame index. For false use null.",
                    "trigger_observed=true means a concrete listed action actually occurs visibly in these frames; use its frame index. A hypothetical possibility is false. Use false and null if that action is absent, unsupported or not visible; do not turn occlusion into proof of omission.",
                )

            def parse(value):
                if set(value["checks"]) != set(self.registry.enabled):
                    raise ValueError("Rule keys mismatch")
                events = []
                for rule_id, item in value["checks"].items():
                    if not item[flag_key]:
                        # A negative finding never becomes evidence. The schema
                        # still bounds any supplied but unused index.
                        continue
                    if item["frame_index"] is None:
                        raise ValueError("Candidate needs index")
                    frame = frames[item["frame_index"]]
                    rule = self.registry.enabled[rule_id]
                    events.append(
                        ScreenCandidate(
                            rule_id=rule_id,
                            event_frame_id=frame["id"],
                            frame_ids=[frame["id"]],
                            predicates={
                                key: True
                                for key in rule.get(
                                    "candidate_triggers", list(rule["predicates"])
                                )
                            },
                            applicable=True,
                        )
                    )
                self.stage_counts["screening_calls"] += 1
                self.stage_counts["possible_triggers"] += len(events)
                return ScreenOutput(
                    events=events, visibility_limited=value["visibility_limited"]
                )

            return self._request(frames, prompt, schema, deadline, private_dir, parse)

        rule = self.registry.enabled[verify.rule_id]
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "observation": {"type": "string", "minLength": 1, "maxLength": 220},
                "predicates": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {k: {"type": "boolean"} for k in rule["predicates"]},
                    "required": list(rule["predicates"]),
                },
                "applicable": {"type": "boolean"},
                "complete_context": {"type": "boolean"},
                "exclusion_present": {"type": "boolean"},
                "event_frame_index": frame_index,
                "evidence_indices": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": frame_index,
                },
                "counterevidence": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {"type": "string", "maxLength": 100},
                },
                "limitations": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {"type": "string", "maxLength": 100},
                },
            },
        }
        schema["required"] = list(schema["properties"])
        conditions = {
            "rule_id": verify.rule_id,
            "applicability": rule["public"]["applicability"],
            "visible_predicates": rule["predicates"],
            "exclusions": rule["public"]["exclusions"],
            "context": rule["context"],
        }
        prompt = (
            "Candidate="
            + verify.rule_id
            + ". Proposed occurrence="
            + json.dumps(self.candidate_focus(frames, verify), separators=(",", ":"))
            + ". Assess THIS occurrence, not another earlier/later occurrence. The proposal is a hint, not proof. "
            + "Assess this proposed event even if it is absent. First describe the directly visible sequence; then truthfully assess EVERY predicate. A proposal is not evidence. A predicate is true only when visually supported. Check a benign explanation and every exclusion. complete_context requires the relevant boundaries/area; occlusion cannot prove an omission. Keep negative/counterevidence in the object; do not skip the assessment. Pick supplied frame indices, with the event index in evidence_indices. No identity, intent, permission or ledger inference.\nConditions="
            + json.dumps(conditions, ensure_ascii=False, separators=(",", ":"))
            + "\nFrame indices="
            + json.dumps(legend, separators=(",", ":"))
            + "\nReturn JSON="
            + json.dumps(schema, separators=(",", ":"))
        )

        def parse(value):
            primary = value["event_frame_index"]
            selected = value["evidence_indices"]
            if primary not in selected:
                # Every index has already passed the supplied-frame enum. The
                # assessed instant is authoritative; include its real source
                # frame, retain up to two selected context frames, and preserve
                # the untouched raw response in the private request record.
                selected = [primary, *selected[:2]]
                self.stage_counts["evidence_link_normalizations"] += 1
            self.stage_counts["verification_assessments"] += 1
            self.stage_counts["incomplete_context"] += not value["complete_context"]
            self.stage_counts["exclusions_present"] += value["exclusion_present"]
            self.stage_counts["missing_predicates"] += not all(
                value["predicates"].values()
            )
            self.stage_counts["eligible_assessments"] += (
                value["applicable"]
                and value["complete_context"]
                and not value["exclusion_present"]
                and all(value["predicates"].values())
            )
            return WindowOutput(
                events=[
                    Observation(
                        rule_id=verify.rule_id,
                        event_frame_id=frames[value["event_frame_index"]]["id"],
                        frame_ids=[frames[i]["id"] for i in selected],
                        predicates=value["predicates"],
                        applicable=value["applicable"],
                        complete_context=value["complete_context"],
                        exclusion_present=value["exclusion_present"],
                        observation=value["observation"],
                        counterevidence=value["counterevidence"],
                        limitations=value["limitations"],
                    )
                ],
                visibility_limited=bool(value["limitations"]),
            )

        return self._request(frames, prompt, schema, deadline, private_dir, parse)
