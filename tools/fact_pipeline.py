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
    QUESTIONS = FACTS
    REUSE_QUESTIONS = False
    DESCRIBE_ACTION = False
    CONFIRM_NO_PEOPLE = False
    SCREEN_VERSION = "visual inventory then independent short action questions v2"

    def __init__(self, model, registry, max_candidates=8):
        super().__init__(model, registry, max_candidates, screen_wording="observed")
        model.runtime_configuration.update(
            experimental_screening=self.SCREEN_VERSION,
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
            person_absence_rechecks=0,
            false_absence_recoveries=0,
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
        allow_questions = scene["people_visible"]
        scene_limited = scene["visibility_limited"]
        if not allow_questions and self.CONFIRM_NO_PEOPLE:
            count_schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "visible_detail": {"type": "string", "maxLength": 80},
                    "people_count": {
                        "anyOf": [
                            {"type": "integer", "minimum": 0, "maximum": 100},
                            {"type": "null"},
                        ]
                    },
                    "visibility_limited": {"type": "boolean"},
                },
                "required": ["visible_detail", "people_count", "visibility_limited"],
            }
            absence_confirmed = True
            for index in sorted({0, len(frames) // 2, len(frames) - 1}):
                count = self._request(
                    [frames[index]],
                    "Briefly name what is visible in this ONE image, then count visible real people OR drawn human stick figures. Human-shaped drawings count as figures here. Abstract colors, numbers and furniture are not people. If not resolvable use null, not zero. JSON="
                    + json.dumps(count_schema, separators=(",", ":")),
                    count_schema,
                    deadline,
                    private_dir,
                    lambda value: value,
                )
                self.stage_counts["person_absence_rechecks"] += 1
                scene_limited |= (
                    count["visibility_limited"] or count["people_count"] is None
                )
                if count["people_count"] is None or count["visibility_limited"]:
                    absence_confirmed = False
                if count["people_count"] is not None and count["people_count"] > 0:
                    allow_questions = True
                    absence_confirmed = False
                    self.stage_counts["false_absence_recoveries"] += 1
                    break
            allow_questions |= not absence_confirmed
        if not allow_questions:
            self.stage_counts["scenes_without_people"] += 1
            self.stage_counts["screening_calls"] += 1
            return ScreenOutput(events=[], visibility_limited=scene_limited)
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
        if self.DESCRIBE_ACTION:
            schema["properties"] = {
                "visible_change": {"type": "string", "maxLength": 120},
                **schema["properties"],
            }
            schema["required"] = ["visible_change", *schema["required"]]
        legend = [
            {"index": i, "seconds": round(f["timestamp_sec"], 6)}
            for i, f in enumerate(frames)
        ]
        events = []
        answers = {}
        limited = scene_limited
        for key, rule in self.registry.enabled.items():
            question = self.QUESTIONS.get(key, " / ".join(rule["predicates"].values()))
            prompt = (
                "Watch these ordered source frames. Answer ONLY this visual question: "
                + question
                + " Does that specific action actually occur? Do not substitute a similar action. "
                "This is not a legal verdict. If yes, select the FIRST supportable source frame of EACH distinct occurrence. "
                "For a continuous action select its onset once, not every frame. Never select preceding context. "
                "If absent or unobservable, observed=false; if unobservable set visibility_limited=true. "
                "Return up to three event indices; if more distinct occurrences need representation set overflow=true. "
                "Do not infer identity, authorization, ledger data or unseen actions. "
                + (
                    "First state the directly visible change relevant to this ONE question in visible_change, "
                    "then answer observed and select its actual source indices. A hypothetical possibility is not observed. "
                    if self.DESCRIBE_ACTION
                    else "Answer briefly without a description. "
                )
                + "Source indices="
                + json.dumps(legend, separators=(",", ":"))
                + " JSON="
                + json.dumps(schema, separators=(",", ":"))
            )

            def parse(value):
                if value["observed"] and not value["indices"] and not value["overflow"]:
                    raise ValueError("Observed action needs a real source instant")
                return value

            cache_key = question if self.REUSE_QUESTIONS else key
            if cache_key not in answers:
                answers[cache_key] = self._request(
                    frames, prompt, schema, deadline, private_dir, parse
                )
                self.stage_counts["question_calls"] += 1
            value = answers[cache_key]
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


class TriggerFactPipeline(FactPipeline):
    """Visible action proposals only; the inherited final legal verifier is unchanged."""

    REUSE_QUESTIONS = True
    DESCRIBE_ACTION = True
    CONFIRM_NO_PEOPLE = True

    SCREEN_VERSION = "visual trigger proposals v5; confirm negative people inventory on separate source frames; direct visual change before decision"
    QUESTIONS = {
        "NB231-22": FACTS["NB231-22"],
        "NB231-20-PRESENCE": "A person visibly counts, sorts or packs banknotes or coins. Merely touching a desk or handling ordinary papers is not cash handling. Customer presence does not determine whether this action occurs.",
        "NB231-21": "Cash and two or more separate paper documents are visibly handled together in one handover. This question does not require reading the documents or amounts and does not establish combined accounting.",
        "NB231-20-STORAGE": "Visible cash remains exposed on a work surface while a person changes to another activity. This does not establish whose money it is or whether any transaction has ended.",
        "NB231-24": FACTS["NB231-24"],
        "NB231-25": "A cash bag is visibly opened or its contents are visibly counted. This question does not require visible damage and does not establish anybody's absence or identity.",
        "NB231-42": "A person visibly counts, sorts or packs banknotes or coins. Merely touching a desk or handling ordinary papers is not cash handling. Customer presence does not determine whether this action occurs.",
    }
