from pathlib import Path
import json
import uuid
import copy
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .. import media
from ..contracts import validate_result
from ..errors import ProcessingError
from ..reproducibility import configuration


class ScreenCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str
    event_frame_id: str
    frame_ids: list[str] = Field(min_length=1, max_length=3)
    predicates: dict[str, StrictBool]
    applicable: StrictBool


class Observation(ScreenCandidate):
    complete_context: StrictBool
    exclusion_present: StrictBool
    observation: str = Field(min_length=1, max_length=300)
    counterevidence: list[Annotated[str, Field(max_length=100)]] = Field(max_length=4)
    limitations: list[Annotated[str, Field(max_length=100)]] = Field(max_length=4)


class WindowOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[Observation] = Field(max_length=16)
    visibility_limited: StrictBool


class ScreenOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[ScreenCandidate] = Field(max_length=16)
    visibility_limited: StrictBool


class TriggerAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trigger_possible: StrictBool
    event_frame_id: str | None
    frame_ids: list[str] = Field(max_length=3)


class AssessmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_activity: str = Field(max_length=240)
    assessments: dict[str, TriggerAssessment]
    visibility_limited: StrictBool


def windows(duration, size=14.0, overlap=2.0):
    start = 0.0
    while start < duration:
        end = min(start + size, duration)
        yield start, end
        if end == duration:
            break
        start = end - overlap


class Pipeline:
    def __init__(self, model, registry, max_candidates=8):
        self.model, self.registry, self.max_candidates = model, registry, max_candidates
        self.configuration = configuration(
            max_candidates,
            registry.path,
            getattr(model, "manifest", None),
            getattr(model, "runtime_configuration", None),
        )

    def ask(self, frames, verify, deadline, private_dir):
        if not verify and self.configuration.get("screening_mode") == "assessments":
            return self.ask_assessments(frames, deadline, private_dir)
        schema = WindowOutput if verify else ScreenOutput
        output_schema = schema.model_json_schema()
        event_type = "Observation" if verify else "ScreenCandidate"
        base_event = output_schema.pop("$defs")[event_type]
        variants = []
        selected_rules = (
            {verify.rule_id: self.registry.enabled[verify.rule_id]}
            if verify
            else self.registry.enabled
        )
        for rule_id, rule in selected_rules.items():
            event_schema = copy.deepcopy(base_event)
            properties = event_schema["properties"]
            properties["rule_id"] = {"type": "string", "enum": [rule_id]}
            frame_type = {"type": "string", "enum": [frame["id"] for frame in frames]}
            properties["event_frame_id"] = frame_type
            properties["frame_ids"]["items"] = frame_type
            predicate_keys = (
                list(rule["predicates"])
                if verify
                else rule.get("candidate_triggers", list(rule["predicates"]))
            )
            properties["predicates"] = {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "boolean"} for key in predicate_keys},
                "required": predicate_keys,
            }
            variants.append(event_schema)
        if not verify and len(variants) > 1:
            event_schema = copy.deepcopy(variants[0])
            event_schema["properties"]["rule_id"]["enum"] = list(selected_rules)
            predicates = event_schema["properties"]["predicates"]
            predicates["properties"] = {
                key: value
                for variant in variants
                for key, value in variant["properties"]["predicates"][
                    "properties"
                ].items()
            }
            predicates["required"] = []
            # The grammar permits the known vocabulary; exact per-rule key sets
            # are validated below, with at most one repair. Avoid duplicating all
            # frame-ID enums per rule in the GPU prompt.
            output_schema["properties"]["events"]["items"] = event_schema
        else:
            output_schema["properties"]["events"]["items"] = variants[0]

        def compact(value):
            if isinstance(value, dict):
                return {
                    key: compact(item) for key, item in value.items() if key != "title"
                }
            if isinstance(value, list):
                return [compact(item) for item in value]
            return value

        output_schema = compact(output_schema)
        prompt_rules = [
            rule for rule in self.registry.prompt() if rule["rule_id"] in selected_rules
        ]
        if not verify:
            for rule in prompt_rules:
                rule["predicates"] = {
                    key: value
                    for key, value in rule["predicates"].items()
                    if key in rule["candidate_triggers"]
                }
        mode = (
            "Verify the proposed possible event AND a plausible benign explanation in its full temporal context."
            if verify
            else "Screen the entire interval for a possible visible action/omission trigger from a listed rule. Report only candidate_triggers predicates at screening. At screening, applicable means the action/setting could be relevant; leave complete legal/context applicability to the later verifier. Include low-motion omissions only with complete visible sequence."
        )
        prompt = (
            mode
            + ' Return ONLY plausible event candidates, never one entry per frame or negative findings. If no plausible event, return {"events":[],"visibility_limited":false} (set visibility_limited truthfully). Keep text brief. Select frame IDs verbatim. event_frame_id must be one of the evidence frame_ids: choose the action instant or first supportable omission, never preceding context. Include before/action/after evidence where available. Evaluate every predicate. Occlusion does not prove an omission. Generic anomalies are not legal violations.\nRules='
            + json.dumps(
                prompt_rules,
                ensure_ascii=False,
            )
            + "\nJSON schema="
            + json.dumps(output_schema, separators=(",", ":"))
        )
        if verify:
            prompt += "\nCandidate=" + verify.model_dump_json()
        else:
            prompt += "\nFinal instruction: An ongoing service alone is not an event. If none of a rule's candidate_triggers is visibly true, return an empty events array. Never enumerate individual frames or normal ongoing states."
        raw = self.model.infer(frames, prompt, deadline, output_schema=output_schema)
        # Prompts/outputs stay in ignored per-case storage; exceptions never include them.
        private_dir.mkdir(exist_ok=True)
        for attempt in range(2):
            (private_dir / f"{uuid.uuid4().hex}.json").write_text(
                json.dumps({"prompt": prompt, "output": raw}, ensure_ascii=False),
                encoding="utf-8",
            )
            try:
                text = raw.strip()
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                output = schema.model_validate_json(text.strip())
                allowed = {f["id"] for f in frames}
                for event in output.events:
                    if (
                        event.rule_id not in self.registry.enabled
                        or not set(event.frame_ids) <= allowed
                    ):
                        raise ValueError()
                    if event.event_frame_id not in event.frame_ids:
                        raise ValueError()
                    rule = self.registry.enabled[event.rule_id]
                    expected = set(
                        rule["predicates"]
                        if verify
                        else rule.get("candidate_triggers", list(rule["predicates"]))
                    )
                    if set(event.predicates) != expected:
                        raise ValueError()
                return output
            except Exception:
                if attempt:
                    raise ProcessingError(
                        "MODEL_OUTPUT_INVALID", "Model output failed validation"
                    ) from None
                raw = self.model.infer(
                    frames,
                    prompt
                    + "\nPrevious response failed schema or allowed-ID validation. Return one corrected JSON object only.",
                    deadline,
                    output_schema=output_schema,
                )

    def ask_assessments(self, frames, deadline, private_dir):
        frame_type = {"type": "string", "enum": [frame["id"] for frame in frames]}
        assessment_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "trigger_possible": {"type": "boolean"},
                "event_frame_id": {"anyOf": [frame_type, {"type": "null"}]},
                "frame_ids": {"type": "array", "maxItems": 3, "items": frame_type},
            },
            "required": ["trigger_possible", "event_frame_id", "frame_ids"],
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "observed_activity": {"type": "string", "maxLength": 240},
                "assessments": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        key: assessment_schema for key in self.registry.enabled
                    },
                    "required": list(self.registry.enabled),
                },
                "visibility_limited": {"type": "boolean"},
            },
            "required": ["observed_activity", "assessments", "visibility_limited"],
        }
        rules = [
            {
                "rule_id": key,
                "trigger_mode": rule.get("candidate_trigger_mode", "any"),
                "observable_triggers": {
                    trigger: rule.get("screening_descriptions", {}).get(
                        trigger, rule["predicates"][trigger]
                    )
                    for trigger in rule.get(
                        "candidate_triggers", list(rule["predicates"])
                    )
                },
            }
            for key, rule in self.registry.enabled.items()
        ]
        prompt = (
            "Observe the sequence in time order. First briefly describe directly visible actions in observed_activity, without legal conclusions. Then assess EACH listed action trigger. trigger_possible means the action could visibly occur; full legal applicability will be checked separately. For a possible trigger, provide actual frame IDs including its instant. Otherwise use false, null and an empty frame_ids array. Do not invent actions or infer identity, intent or authority. Report visibility limits. Return one compact JSON object.\nAction triggers="
            + json.dumps(rules, separators=(",", ":"))
            + "\nSchema="
            + json.dumps(schema, separators=(",", ":"))
        )
        private_dir.mkdir(exist_ok=True)
        raw = self.model.infer(frames, prompt, deadline, output_schema=schema)
        for attempt in range(2):
            (private_dir / f"{uuid.uuid4().hex}.json").write_text(
                json.dumps({"prompt": prompt, "output": raw}, ensure_ascii=False),
                encoding="utf-8",
            )
            try:
                result = AssessmentOutput.model_validate_json(raw)
                if set(result.assessments) != set(self.registry.enabled):
                    raise ValueError()
                allowed = {frame["id"] for frame in frames}
                events = []
                for rule_id, item in result.assessments.items():
                    if not set(item.frame_ids) <= allowed or (
                        item.event_frame_id is not None
                        and item.event_frame_id not in allowed
                    ):
                        raise ValueError()
                    if not item.trigger_possible:
                        continue
                    if item.event_frame_id not in item.frame_ids or not item.frame_ids:
                        raise ValueError()
                    rule = self.registry.enabled[rule_id]
                    events.append(
                        ScreenCandidate(
                            rule_id=rule_id,
                            event_frame_id=item.event_frame_id,
                            frame_ids=item.frame_ids,
                            applicable=True,
                            predicates={
                                key: True
                                for key in rule.get(
                                    "candidate_triggers", list(rule["predicates"])
                                )
                            },
                        )
                    )
                return ScreenOutput(
                    events=events, visibility_limited=result.visibility_limited
                )
            except Exception:
                if attempt:
                    raise ProcessingError(
                        "MODEL_OUTPUT_INVALID", "Screening assessment failed validation"
                    ) from None
                raw = self.model.infer(
                    frames,
                    prompt
                    + "\nCorrect the response: every listed rule exactly once; valid actual frame IDs; one JSON object only.",
                    deadline,
                    output_schema=schema,
                )

    def run(
        self, source: Path, directory: Path, job_id: str, deadline: float, progress
    ):
        (directory / "configuration.json").write_text(
            json.dumps(self.configuration, indent=2), encoding="utf-8"
        )
        if not self.registry.enabled:
            raise ProcessingError(
                "ANALYSIS_INCOMPLETE", "No verified rule categories are enabled"
            )
        progress(stage="decoding", progress_percent=None)
        timeline = media.decode_timeline(source, deadline)
        progress(duration_sec=timeline.duration)
        (directory / "source-timeline.json").write_text(
            json.dumps(timeline.__dict__), encoding="utf-8"
        )
        coarse = media.extract(
            source,
            timeline,
            media.sample_indices(timeline),
            directory / "coarse",
            deadline,
        )
        plan = list(
            windows(
                timeline.duration,
                self.configuration["screening_window_sec"],
                self.configuration["screening_overlap_sec"],
            )
        )
        candidates, coverage = [], []
        for n, (start, end) in enumerate(plan):
            progress(stage="screening", progress_percent=100 * n / len(plan))
            frames = [
                f for f in coarse.values() if start - 0.05 <= f["timestamp_sec"] < end
            ]
            output = self.ask(frames, None, deadline, directory / "private-inference")
            for event in output.events:
                rule = self.registry.enabled[event.rule_id]
                trigger_values = list(event.predicates.values())
                trigger = (
                    all(trigger_values)
                    if rule.get("candidate_trigger_mode") == "all"
                    else any(trigger_values)
                )
                if event.applicable and trigger:
                    candidates.append(event)
            scope = "Проверяются только включенные категории правил; отрицательный результат не подтверждает соблюдение всех процедур."
            coverage.append(
                dict(
                    start_sec=start,
                    end_sec=end,
                    state="limited" if output.visibility_limited else "assessed",
                    reason=(
                        "Ограниченная видимость. " if output.visibility_limited else ""
                    )
                    + scope,
                )
            )
        # Merge only same-rule overlapping candidates, never different simultaneous types.
        merged = []
        for event in candidates:
            if any(
                other.rule_id == event.rule_id
                and set(other.frame_ids) & set(event.frame_ids)
                for other in merged
            ):
                continue
            merged.append(event)
        if len(merged) > self.max_candidates:
            raise ProcessingError(
                "RESOURCE_EXHAUSTED",
                "Candidate verification budget exceeded; analysis incomplete",
            )
        accepted = []
        for n, candidate in enumerate(merged):
            progress(stage="verifying", progress_percent=100 * n / max(1, len(merged)))
            t = coarse[candidate.event_frame_id]["timestamp_sec"]
            radius = self.configuration["verification_context_radius_sec"]
            dense_radius = self.configuration["verification_dense_radius_sec"]
            start, end = max(0, t - radius), min(timeline.duration, t + radius)
            dense_indices = set(
                media.sample_indices(
                    timeline,
                    max(start, t - dense_radius),
                    min(end, t + dense_radius),
                    self.configuration["verification_dense_fps"],
                )
            )
            dense_indices.update(
                timeline.nearest(point)
                for point in [
                    start,
                    max(start, t - 6),
                    t,
                    min(end, t + 6),
                    max(start, end - 0.001),
                ]
            )
            dense = media.extract(
                source,
                timeline,
                sorted(dense_indices),
                directory / f"verify-{n}",
                deadline,
            )
            # Dense action interval plus wider before/after anchors; never truncate.
            dense_values = list(dense.values())
            verified = self.ask(
                dense_values, candidate, deadline, directory / "private-inference"
            )
            for event in verified.events:
                if event.rule_id != candidate.rule_id:
                    continue
                if not (
                    event.applicable
                    and event.complete_context
                    and not event.exclusion_present
                    and all(event.predicates.values())
                ):
                    continue
                frames = [dense[i] for i in event.frame_ids]
                timecode = dense[event.event_frame_id]["timestamp_sec"]
                if any(
                    old[0].rule_id == event.rule_id and abs(old[1] - timecode) < 1
                    for old in accepted
                ):
                    continue
                accepted.append((event, timecode, frames, start, end))
        progress(stage="packaging", progress_percent=None)
        accepted.sort(key=lambda item: item[1])
        violations, events = [], []
        snapshots = {key: rule["public"] for key, rule in self.registry.enabled.items()}
        source_dir = directory / "rule-sources"
        source_dir.mkdir(exist_ok=True)
        for rule in self.registry.enabled.values():
            source = (self.registry.path.parent / rule["snapshot"]).read_bytes()
            (source_dir / (rule["public"]["source_sha256"] + ".txt")).write_bytes(
                source
            )
        for i, (observation, t, frames, start, end) in enumerate(accepted):
            rule = self.registry.enabled[observation.rule_id]
            public = rule["public"]
            snapshots[public["rule_id"]] = public
            ev = [media.evidence(f) for f in frames]
            description = observation.observation + " " + rule["template"]
            violations.append(
                dict(
                    type=public["display_name"],
                    timecode_sec=t,
                    description=description,
                    evidence_frames=ev,
                )
            )
            event_id = uuid.uuid4().hex
            events.append(
                dict(
                    event_id=event_id,
                    jury_violation_index=i,
                    type=public["display_name"],
                    timecode_sec=t,
                    context_start_sec=start,
                    context_end_sec=end,
                    observation=observation.observation,
                    rationale=rule["template"],
                    limitations=observation.limitations,
                    counterevidence=observation.counterevidence,
                    rule_ids=[public["rule_id"]],
                    evidence_frames=ev,
                    review=dict(
                        event_id=event_id,
                        decision="unreviewed",
                        note="",
                        updated_at=None,
                    ),
                )
            )
        result = dict(
            job_id=job_id,
            status="done",
            verdict="violation" if violations else "no_violation",
            violations=violations,
        )
        validate_result(result, timeline.duration)
        return dict(
            model_result=result,
            events=events,
            rules=list(snapshots.values()),
            coverage=coverage,
        ), timeline
