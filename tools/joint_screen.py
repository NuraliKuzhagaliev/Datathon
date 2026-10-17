"""Short, detailed joint action screening; unchanged AtomicFact final gates."""

import hashlib
import json
from pathlib import Path
import uuid

from atomic_verifier import AtomicFactPipeline
from cashproof.errors import ProcessingError
from cashproof.inference.pipeline import ScreenCandidate, ScreenOutput
from cashproof.reproducibility import configuration


class JointScreenPipeline(AtomicFactPipeline):
    def __init__(self, model, registry, max_candidates=32, use_motion_views=False):
        super().__init__(model, registry, max_candidates)
        model.runtime_configuration.update(
            experimental_screening="short joint visible-action screen v2; explicit exact-question decision and visual-context continuation merging",
            joint_screen_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            screening_window_sec=7,
            screening_overlap_sec=1,
            screening_max_pixels=131072 if use_motion_views else 393472,
            verification_max_pixels=393472,
            screening_max_new_tokens=1024,
            auxiliary_motion_screen_views=use_motion_views,
        )
        self.configuration = configuration(
            max_candidates,
            registry.path,
            getattr(model, "manifest", None),
            model.runtime_configuration,
        )
        self.stage_counts.update(
            joint_screen_calls=0, raw_joint_proposals=0, merged_visible_continuations=0
        )
        self.screen_episodes = []
        self.use_motion_views = use_motion_views

    def run(self, *args, **kwargs):
        self.screen_episodes = []
        return super().run(*args, **kwargs)

    def ask(self, frames, verify, deadline, private_dir):
        if verify:
            return super().ask(frames, verify, deadline, private_dir)
        if not frames:
            raise ProcessingError("ANALYSIS_INCOMPLETE", "No screening frames")
        source_frames = frames
        if self.use_motion_views:
            from motion_views import pairs

            frames, _ = pairs(
                frames, private_dir.parent / ("screen-motion-" + uuid.uuid4().hex)
            )
        index = {"type": "integer", "enum": list(range(len(frames)))}
        event = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "onset_index": index,
                "last_active_index": index,
                "continues_from_window_start": {"type": "boolean"},
            },
            "required": [
                "onset_index",
                "last_active_index",
                "continues_from_window_start",
            ],
        }
        assessment = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visible_change": {"type": "string", "maxLength": 100},
                "observed": {"type": "boolean"},
                "events": {"type": "array", "maxItems": 3, "items": event},
                "unclear": {"type": "boolean"},
                "overflow": {"type": "boolean"},
            },
            "required": ["visible_change", "observed", "events", "unclear", "overflow"],
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visible_sequence": {"type": "string", "maxLength": 180},
                "customer_area_state": {
                    "type": "string",
                    "enum": [
                        "customer_visible",
                        "fully_visible_empty",
                        "not_fully_visible",
                        "mixed",
                        "not_applicable",
                    ],
                },
                "activity_context": {
                    "type": "string",
                    "enum": [
                        "handover",
                        "ongoing_service",
                        "internal_handling",
                        "transition",
                        "mixed",
                        "unclear",
                    ],
                },
                "worker_area_state": {
                    "type": "string",
                    "enum": [
                        "at_station",
                        "departed",
                        "mixed",
                        "unclear",
                        "not_applicable",
                    ],
                },
                "checks": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {key: assessment for key in self.registry.enabled},
                    "required": list(self.registry.enabled),
                },
                "visibility_limited": {"type": "boolean"},
            },
            "required": [
                "visible_sequence",
                "customer_area_state",
                "activity_context",
                "worker_area_state",
                "checks",
                "visibility_limited",
            ],
        }
        questions = {
            key: self.QUESTIONS.get(key, " / ".join(rule["predicates"].values()))
            for key, rule in self.registry.enabled.items()
        }
        prompt = (
            "Describe the directly visible sequence, then answer every short visual-action question independently. "
            "For each question, observed=true ONLY when that EXACT action actually occurs, including its stated direction and object constraints. "
            "A different or opposite action does not satisfy the question, even if it is clearly visible. "
            "If absent or unobservable, observed=false and events=[]; if unobservable also set unclear=true. "
            "This is candidate screening, not a legal verdict. The question's visible action will be checked against legal conditions later. "
            "Do not require unseen accounting, permission, participant identity or all legal conditions at screening. "
            "A still pose or hypothetical possibility is not an observed action. An empty events list means no visible action for that question. "
            "For EACH distinct occurrence satisfying the exact question select its FIRST supportable local onset_index and last_active_index. "
            "Earlier context or preparatory motion is not yet support for the requested action. "
            "If an action is already visibly in progress in the FIRST image and continues, set continues_from_window_start=true and onset_index=0. "
            "A later new occurrence is separate, even if the question is the same. "
            "Choose mixed context states whenever the relevant visible state changes in this interval. "
            "Never infer customer absence from a cropped or occluded customer area. "
            "Set overflow if more than three occurrences of one question need representation; do not silently truncate. "
            "Questions="
            + json.dumps(questions, separators=(",", ":"))
            + "\nFull frames and auxiliary crops can share one source instant. Use full frames for context; a crop cannot establish absence outside it. Repeated times are views of one instant.\nSource indices="
            + json.dumps(
                [
                    {
                        "index": i,
                        "source_seconds": f["timestamp_sec"],
                        "view": f.get("view_kind", "full"),
                        "crop_box": f.get("source_crop_box"),
                    }
                    for i, f in enumerate(frames)
                ],
                separators=(",", ":"),
            )
            + "\nJSON="
            + json.dumps(schema, separators=(",", ":"))
        )

        def parse(value):
            for result in value["checks"].values():
                if (
                    result["observed"] != bool(result["events"])
                    and not result["overflow"]
                ):
                    raise ValueError(
                        "Exact-action decision must match its source occurrences"
                    )
                for item in result["events"]:
                    if item["last_active_index"] < item["onset_index"] or (
                        item["continues_from_window_start"]
                        and frames[item["onset_index"]]["timestamp_sec"]
                        != frames[0]["timestamp_sec"]
                    ):
                        raise ValueError("Inconsistent source occurrence interval")
            return value

        result = self._request(frames, prompt, schema, deadline, private_dir, parse)
        fingerprint = tuple(
            result[key]
            for key in ("customer_area_state", "activity_context", "worker_area_state")
        )
        limited = result["visibility_limited"]
        candidates = []
        for rule_id, assessment in result["checks"].items():
            if assessment["overflow"]:
                raise ProcessingError(
                    "RESOURCE_EXHAUSTED", "Joint visual event budget exceeded"
                )
            limited |= assessment["unclear"]
            rule = self.registry.enabled[rule_id]
            for event in assessment["events"]:
                self.stage_counts["raw_joint_proposals"] += 1
                first_view, last = (
                    frames[event["onset_index"]],
                    frames[event["last_active_index"]],
                )
                first = next(
                    f
                    for f in source_frames
                    if f["id"] == first_view.get("source_frame_id", first_view["id"])
                )
                previous = next(
                    (
                        e
                        for e in reversed(self.screen_episodes)
                        if e["rule"] == rule_id
                        and e["context"] == fingerprint
                        and e["end"] >= first["timestamp_sec"]
                    ),
                    None,
                )
                clear_context = not limited and not any(
                    state in {"mixed", "unclear", "not_fully_visible"}
                    for state in fingerprint
                )
                if (
                    event["continues_from_window_start"]
                    and previous is not None
                    and clear_context
                ):
                    previous["end"] = max(previous["end"], last["timestamp_sec"])
                    self.stage_counts["merged_visible_continuations"] += 1
                    continue
                self.screen_episodes.append(
                    {
                        "rule": rule_id,
                        "context": fingerprint,
                        "end": last["timestamp_sec"],
                    }
                )
                candidates.append(
                    ScreenCandidate(
                        rule_id=rule_id,
                        event_frame_id=first["id"],
                        frame_ids=[first["id"]],
                        predicates={
                            key: True
                            for key in rule.get(
                                "candidate_triggers", list(rule["predicates"])
                            )
                        },
                        applicable=True,
                    )
                )
        if len(candidates) > 16:
            raise ProcessingError(
                "RESOURCE_EXHAUSTED", "Joint visual event budget exceeded"
            )
        self.stage_counts["joint_screen_calls"] += 1
        self.stage_counts["screening_calls"] += 1
        self.stage_counts["possible_triggers"] += len(candidates)
        return ScreenOutput(events=candidates, visibility_limited=limited)
