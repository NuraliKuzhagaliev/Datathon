"""Development-only visual fact screen, followed by unchanged legal verification."""

import hashlib
import json
from pathlib import Path
from compact_pipeline import CompactPipeline
from cashproof.errors import ProcessingError
from cashproof.inference.pipeline import ScreenCandidate, ScreenOutput
from cashproof.reproducibility import configuration


FACTS = {
    "NB231-22": "A worker actually walks away from the counter/work area during the sequence. Standing, turning or reaching within it is not walking away.",
    "NB231-20-PRESENCE": "Cash is received or counted while the relevant customer area is fully visible and no customer is present. A customer outside view is unknown, not absent.",
    "NB231-20-STORAGE": "A customer service visibly ends and another starts while the earlier cash remains exposed on the work surface. Cash for the current service alone is not this transition.",
    "NB231-21": "Cash belonging to two separately legible incoming documents is accepted together rather than separately. Unreadable documents or invisible electronic steps cannot establish this action.",
    "NB231-24": "A sealed cash-collection bag is handed over or received. This is only the visible handover, not a claim that inspection was omitted.",
    "NB231-25": "A visibly damaged cash-collection bag is opened and its contents counted. Do not guess damage or participant identity.",
    "NB231-42": "Cash is internally counted or packed with only one worker visible in the complete relevant work area. Ordinary customer payment/receipt is not internal packing.",
}


class FactPipeline(CompactPipeline):
    def __init__(self, model, registry, max_candidates=8):
        super().__init__(model, registry, max_candidates, screen_wording="observed")
        model.runtime_configuration.update(
            experimental_screening="visual inventory then independent short action questions v2",
            fact_pipeline_sha256=hashlib.sha256(
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
            fact_observed=0,
            fact_absent=0,
            fact_unclear=0,
            scene_calls=0,
            scenes_without_people=0,
            question_calls=0,
        )

    def ask(self, frames, verify, deadline, private_dir):
        if verify:
            return super().ask(frames, verify, deadline, private_dir)
        if not frames:
            raise ProcessingError("ANALYSIS_INCOMPLETE", "No sampled frames")
        scene_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sequence": {"type": "string", "maxLength": 120},
                "people_visible": {"type": "boolean"},
                "visibility_limited": {"type": "boolean"},
            },
            "required": ["sequence", "people_visible", "visibility_limited"],
        }
        scene = self._request(
            frames,
            "Describe only the actually visible objects and changes in these images, in one short sentence. "
            "Are any real people or drawn human figures visible? Abstract patterns, numbers, machines and furniture alone are not people. "
            "Do not assume a bank, money or a workflow. Return JSON="
            + json.dumps(scene_schema, separators=(",", ":")),
            scene_schema,
            deadline,
            private_dir,
            lambda value: value,
        )
        self.stage_counts["scene_calls"] += 1
        if not scene["people_visible"]:
            self.stage_counts["scenes_without_people"] += 1
            self.stage_counts["screening_calls"] += 1
            return ScreenOutput(
                events=[], visibility_limited=scene["visibility_limited"]
            )
        frame_index = {"type": "integer", "enum": list(range(len(frames)))}
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "observed": {"type": "boolean"},
                "indices": {
                    "type": "array",
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": frame_index,
                },
                "visibility_limited": {"type": "boolean"},
                "overflow": {"type": "boolean"},
            },
            "required": ["observed", "indices", "visibility_limited", "overflow"],
        }
        legend = [
            {"index": i, "seconds": round(f["timestamp_sec"], 6)}
            for i, f in enumerate(frames)
        ]
        events = []
        limited = scene["visibility_limited"]
        for key, rule in self.registry.enabled.items():
            question = FACTS.get(key, " / ".join(rule["predicates"].values()))
            prompt = (
                "Watch these ordered source frames. Answer ONLY this visual question: "
                + question
                + " Does that specific action actually occur? Do not substitute a similar action. "
                "This is not a legal verdict. If yes, select the FIRST supportable source frame of EACH distinct occurrence. "
                "For a continuous action select its onset once, not every frame. Never select preceding context. "
                "If absent or unobservable, observed=false; if unobservable set visibility_limited=true. "
                "Return up to three event indices; if more distinct occurrences need representation set overflow=true. "
                "Do not infer identity, authorization, ledger data or unseen actions. "
                "Answer briefly without a description. Source indices="
                + json.dumps(legend, separators=(",", ":"))
                + " JSON="
                + json.dumps(schema, separators=(",", ":"))
            )

            def parse(value):
                if value["observed"] and not value["indices"] and not value["overflow"]:
                    raise ValueError("Observed action needs a real source instant")
                return value

            value = self._request(frames, prompt, schema, deadline, private_dir, parse)
            self.stage_counts["question_calls"] += 1
            if value["overflow"]:
                raise ProcessingError(
                    "RESOURCE_EXHAUSTED",
                    "Visual fact event budget exceeded; analysis incomplete",
                )
            limited |= value["visibility_limited"]
            state = (
                "observed"
                if value["observed"]
                else ("unclear" if value["visibility_limited"] else "absent")
            )
            self.stage_counts["fact_" + state] += 1
            if not value["observed"]:
                continue
            for index in value["indices"]:
                frame = frames[index]
                events.append(
                    ScreenCandidate(
                        rule_id=key,
                        event_frame_id=frame["id"],
                        frame_ids=[frame["id"]],
                        predicates={
                            k: True
                            for k in rule.get(
                                "candidate_triggers", list(rule["predicates"])
                            )
                        },
                        applicable=True,
                    )
                )
        if len(events) > 16:
            raise ProcessingError(
                "RESOURCE_EXHAUSTED",
                "Visual fact event budget exceeded; analysis incomplete",
            )
        self.stage_counts["screening_calls"] += 1
        self.stage_counts["possible_triggers"] += len(events)
        return ScreenOutput(events=events, visibility_limited=limited)
