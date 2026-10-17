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
    "NB231-24": "A sealed cash-collection bag is handed over or received. This is only the visible handover, not a claim that inspection was omitted.",
    "NB231-25": "A visibly damaged cash-collection bag is opened and its contents counted. Do not guess damage or participant identity.",
    "NB231-42": "Cash is internally counted or packed with only one worker visible in the complete relevant work area. Ordinary customer payment/receipt is not internal packing.",
}


class FactPipeline(CompactPipeline):
    def __init__(self, model, registry, max_candidates=8):
        super().__init__(model, registry, max_candidates, screen_wording="observed")
        model.runtime_configuration.update(
            experimental_screening="mandatory observed/absent/unclear visual facts v1",
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
        self.stage_counts.update(fact_observed=0, fact_absent=0, fact_unclear=0)

    def ask(self, frames, verify, deadline, private_dir):
        if verify:
            return super().ask(frames, verify, deadline, private_dir)
        if not frames:
            raise ProcessingError("ANALYSIS_INCOMPLETE", "No sampled frames")
        frame_index = {"type": "integer", "enum": list(range(len(frames)))}
        check = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "state": {"type": "string", "enum": ["observed", "absent", "unclear"]},
                "indices": {
                    "type": "array",
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": frame_index,
                },
            },
            "required": ["state", "indices"],
        }
        keys = list(self.registry.enabled)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sequence": {"type": "string", "maxLength": 160},
                "facts": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {key: check for key in keys},
                    "required": keys,
                },
                "visibility_limited": {"type": "boolean"},
                "overflow": {"type": "boolean"},
            },
            "required": ["sequence", "facts", "visibility_limited", "overflow"],
        }
        questions = {
            key: FACTS.get(
                key, " / ".join(self.registry.enabled[key]["predicates"].values())
            )
            for key in keys
        }
        legend = [
            {"index": i, "seconds": round(frame["timestamp_sec"], 6)}
            for i, frame in enumerate(frames)
        ]
        prompt = (
            "Watch the ordered visual sequence. Describe what changes in one short sentence, then answer EACH visual-fact question. "
            "Do not decide whether a legal violation occurred. Observed means the described action actually occurs visibly; "
            "absent means it does not occur in a sufficiently visible sequence; unclear means it cannot be established. "
            "For observed, supply 1-3 actual frame indices at distinct action instants, not preceding context. "
            "For absent/unclear use an empty indices array. Do not guess cash provenance, identity, permission or invisible steps. "
            "Set overflow=true if more than three distinct action instants for one question cannot fit; never silently truncate. "
            "Pictures without people cannot show any of these human actions. Be specific about visible transitions, not generic unusualness.\n"
            "Questions="
            + json.dumps(questions, separators=(",", ":"))
            + "\nOrdered source times="
            + json.dumps(legend, separators=(",", ":"))
            + "\nReturn JSON="
            + json.dumps(schema, separators=(",", ":"))
        )

        def parse(value):
            events = []
            counts = {"observed": 0, "absent": 0, "unclear": 0}
            for key, item in value["facts"].items():
                if item["state"] == "observed" and not item["indices"]:
                    raise ValueError("Observed fact requires an actual source frame")
                if item["state"] != "observed" and item["indices"]:
                    raise ValueError("Unsupported fact cannot supply event instants")
                counts[item["state"]] += 1
                if item["state"] != "observed":
                    continue
                rule = self.registry.enabled[key]
                for index in item["indices"]:
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
            if len(events) > 16 or value["overflow"]:
                self._fact_overflow = True
                return ScreenOutput(events=[], visibility_limited=True)
            for state, count in counts.items():
                self.stage_counts["fact_" + state] += count
            self.stage_counts["screening_calls"] += 1
            self.stage_counts["possible_triggers"] += len(events)
            return ScreenOutput(
                events=events, visibility_limited=value["visibility_limited"]
            )

        self._fact_overflow = False
        output = self._request(frames, prompt, schema, deadline, private_dir, parse)
        if self._fact_overflow:
            raise ProcessingError(
                "RESOURCE_EXHAUSTED",
                "Visual fact event budget exceeded; analysis incomplete",
            )
        return output
