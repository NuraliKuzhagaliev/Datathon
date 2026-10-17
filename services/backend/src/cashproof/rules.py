import hashlib
import json
from pathlib import Path
from .contracts import validate


class Registry:
    def __init__(self, path: Path):
        self.path = path
        self.document = json.loads(path.read_text(encoding="utf-8"))
        validate(
            "RuleRegistry",
            {
                "version": self.document["version"],
                "rules": [r["public"] for r in self.document["rules"]],
            },
        )
        self.version = self.document["version"]
        self.rules = {r["public"]["rule_id"]: r for r in self.document["rules"]}
        for r in self.rules.values():
            if r["public"]["enabled"]:
                snapshot = (path.parent / r["snapshot"]).resolve()
                if not snapshot.is_relative_to(path.parent.resolve()):
                    raise ValueError("Unsafe rule snapshot path")
                if (
                    hashlib.sha256(snapshot.read_bytes()).hexdigest()
                    != r["public"]["source_sha256"]
                ):
                    raise ValueError("Rule snapshot hash mismatch")
                if not r["public"]["effective_date"] or not r.get("predicates"):
                    raise ValueError("Rule lacks effective date or predicates")
                triggers = r.get("candidate_triggers", list(r["predicates"]))
                if not triggers or not set(triggers) <= set(r["predicates"]):
                    raise ValueError("Rule candidate trigger lacks a defined predicate")

    @property
    def enabled(self):
        return {k: v for k, v in self.rules.items() if v["public"]["enabled"]}

    def public(self):
        return {
            "version": self.version,
            "rules": [v["public"] for v in self.rules.values()],
        }

    def prompt(self):
        return [
            {
                "rule_id": k,
                "applicability": v["public"]["applicability"],
                "predicates": v["predicates"],
                "candidate_triggers": v.get(
                    "candidate_triggers", list(v["predicates"])
                ),
                "context": v["context"],
                "exclusions": v["public"]["exclusions"],
            }
            for k, v in self.enabled.items()
        ]
