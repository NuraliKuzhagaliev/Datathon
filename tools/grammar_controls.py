"""Tokenizer-specific true/false grammar checks using public text only."""

import json

from lmformatenforcer import JsonSchemaParser, CharacterLevelParserConfig
from lmformatenforcer.integrations.transformers import (
    build_transformers_prefix_allowed_tokens_fn,
)


def verify(model, directory):
    directory.mkdir(parents=True, exist_ok=True)
    tokenizer = model.processor.tokenizer
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"flag": {"type": "boolean"}},
        "required": ["flag"],
    }
    results = {}
    for flag in (True, False):
        callback = build_transformers_prefix_allowed_tokens_fn(
            model.tokenizer_data,
            JsonSchemaParser(
                schema, config=CharacterLevelParserConfig(force_json_field_order=True)
            ),
        )
        # Initialize on the prompt before appending output. Jumping directly to
        # the property prefix would instead mark that prefix as prompt tokens.
        sequence = tokenizer.encode("Synthetic JSON answer:", add_special_tokens=False)
        answer = json.dumps({"flag": flag}, separators=(",", ":"))
        accepted = True
        for token in tokenizer.encode(answer, add_special_tokens=False):
            allowed = callback(0, model.torch.tensor(sequence, dtype=model.torch.long))
            if token not in allowed:
                accepted = False
                break
            sequence.append(token)
        if accepted:
            allowed = callback(0, model.torch.tensor(sequence, dtype=model.torch.long))
            accepted = tokenizer.eos_token_id in allowed
        results[str(flag).lower() + "_permitted"] = accepted
    aggregate = {
        "synthetic_grammar_controls": True,
        **results,
        "passed": all(results.values()),
        "meaning": "Both boolean answers are syntactically reachable; not visual accuracy.",
    }
    (directory / "aggregate.json").write_text(
        json.dumps(aggregate, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate), flush=True)
    return aggregate
