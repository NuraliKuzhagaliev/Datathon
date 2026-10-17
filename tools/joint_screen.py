"""Short exact-action proposals; unchanged AtomicFact final legal/evidence gates."""

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
        fps = model.runtime_configuration.get("screening_sample_fps", 1)
        if fps not in {1, 2, 4}:
            raise ValueError("Unqualified screening density")
        model.runtime_configuration.update(
            experimental_screening="short joint exact-action screen v4; first criterion witness; no inferred episode merging",
            joint_screen_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            screening_window_sec=3.5 if fps == 4 else 7,
            screening_overlap_sec=0.5 if fps == 4 else 1,
            screening_max_pixels=131072 if use_motion_views else 393472,
            verification_max_pixels=393472,
            screening_max_new_tokens=768,
            auxiliary_motion_screen_views=use_motion_views,
        )
        self.configuration = configuration(
            max_candidates,
            registry.path,
            getattr(model, "manifest", None),
            model.runtime_configuration,
        )
        self.stage_counts.update(joint_screen_calls=0, raw_joint_proposals=0)
        self.use_motion_views = use_motion_views

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
        observed = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "state": {"type": "string", "enum": ["observed"]},
                "visible_change": {"type": "string", "minLength": 1, "maxLength": 100},
                "event_indices": {
                    "type": "array",
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": index,
                },
                "overflow": {"type": "boolean"},
            },
            "required": ["state", "visible_change", "event_indices", "overflow"],
        }
        assessment = {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "state": {"type": "string", "enum": ["absent", "unclear"]}
                    },
                    "required": ["state"],
                },
                observed,
            ]
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "visible_sequence": {"type": "string", "maxLength": 180},
                "checks": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {key: assessment for key in self.registry.enabled},
                    "required": list(self.registry.enabled),
                },
                "visibility_limited": {"type": "boolean"},
            },
            "required": ["visible_sequence", "checks", "visibility_limited"],
        }
        questions = {
            key: self.QUESTIONS.get(key, " / ".join(rule["predicates"].values()))
            for key, rule in self.registry.enabled.items()
        }
        prompt = (
            "Describe directly visible changes, then answer EACH exact visual question independently. "
            "This is candidate screening, not a legal verdict. Do not require unseen accounting, permission or all legal conditions. "
            "state=observed means the EXACT requested action actually occurs, including its direction and object constraints. "
            "A different/opposite action is absent for that question. If evidence is insufficient use unclear. "
            "Absent/unclear answers contain only state. An observed answer needs actual event_indices, visible_change and overflow. "
            "Each event index is the FIRST supplied image establishing the question's criterion for one distinct occurrence. "
            "Do not select preceding context, the start of generic motion, or merely a person/object already present. "
            "A second occurrence after the criterion resets needs its own index. A continuous occurrence is represented once. "
            "If more than three occurrences of one question need representation set overflow=true; never silently truncate. "
            "Do not infer identity, intent, authority or events outside the images. Use full frames for context; a crop cannot establish absence outside it. "
            "Repeated source times are views of one instant. Return compact JSON.\nSource indices="
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
            + "\nExact questions="
            + json.dumps(questions, separators=(",", ":"))
            + "\nAn event is a witness of its EXACT question, not any visible activity."
        )

        def parse(value):
            for result in value["checks"].values():
                if (
                    result["state"] == "observed"
                    and not result["event_indices"]
                    and not result["overflow"]
                ):
                    raise ValueError("Observed action requires a source witness")
            return value

        result = self._request(frames, prompt, schema, deadline, private_dir, parse)
        limited = result["visibility_limited"]
        candidates = []
        for rule_id, assessment in result["checks"].items():
            limited |= assessment["state"] == "unclear"
            if assessment["state"] != "observed":
                continue
            if assessment["overflow"]:
                raise ProcessingError(
                    "RESOURCE_EXHAUSTED", "Joint visual event budget exceeded"
                )
            rule = self.registry.enabled[rule_id]
            for i in assessment["event_indices"]:
                self.stage_counts["raw_joint_proposals"] += 1
                view = frames[i]
                original = next(
                    f
                    for f in source_frames
                    if f["id"] == view.get("source_frame_id", view["id"])
                )
                candidates.append(
                    ScreenCandidate(
                        rule_id=rule_id,
                        event_frame_id=original["id"],
                        frame_ids=[original["id"]],
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
