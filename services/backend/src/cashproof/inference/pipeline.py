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
            max_candidates, registry.path, getattr(model, "manifest", None)
        )

    def ask(self, frames, verify, deadline, private_dir):
        schema = WindowOutput if verify else ScreenOutput
        output_schema = schema.model_json_schema()
        event_type = "Observation" if verify else "ScreenCandidate"
        base_event = output_schema.pop("$defs")[event_type]
        variants = []
        for rule_id, rule in self.registry.enabled.items():
            event_schema = copy.deepcopy(base_event)
            properties = event_schema["properties"]
            properties["rule_id"] = {"type": "string", "enum": [rule_id]}
            frame_type = {"type": "string", "enum": [frame["id"] for frame in frames]}
            properties["event_frame_id"] = frame_type
            properties["frame_ids"]["items"] = frame_type
            properties["predicates"] = {
                "type": "object",
                "additionalProperties": False,
                "properties": {key: {"type": "boolean"} for key in rule["predicates"]},
                "required": list(rule["predicates"]),
            }
            variants.append(event_schema)
        output_schema["properties"]["events"]["items"] = {"anyOf": variants}
        mode = (
            "Verify the proposed possible event AND a plausible benign explanation in its full temporal context."
            if verify
            else "Screen this entire interval for candidates supported by a listed rule. Include low-motion omissions only with complete visible sequence."
        )
        prompt = (
            mode
            + ' Return ONLY plausible event candidates, never one entry per frame or negative findings. If no plausible event, return {"events":[],"visibility_limited":false} (set visibility_limited truthfully). Keep text brief. Select frame IDs verbatim. event_frame_id must be one of the evidence frame_ids: choose the action instant or first supportable omission, never preceding context. Include before/action/after evidence where available. Evaluate every predicate. Occlusion does not prove an omission. Generic anomalies are not legal violations.\nRules='
            + json.dumps(self.registry.prompt(), ensure_ascii=False)
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
                    expected = set(self.registry.enabled[event.rule_id]["predicates"])
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
        plan = list(windows(timeline.duration))
        candidates, coverage = [], []
        for n, (start, end) in enumerate(plan):
            progress(stage="screening", progress_percent=100 * n / len(plan))
            frames = [
                f for f in coarse.values() if start - 0.05 <= f["timestamp_sec"] < end
            ]
            output = self.ask(frames, None, deadline, directory / "private-inference")
            candidates.extend(
                event
                for event in output.events
                if event.applicable
                and any(
                    event.predicates[key]
                    for key in self.registry.enabled[event.rule_id].get(
                        "candidate_triggers", list(event.predicates)
                    )
                )
            )
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
            start, end = max(0, t - 12), min(timeline.duration, t + 12)
            dense_indices = set(
                media.sample_indices(timeline, max(start, t - 2), min(end, t + 2), 2)
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
