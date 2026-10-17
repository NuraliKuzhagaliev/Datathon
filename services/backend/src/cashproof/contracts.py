import base64
from io import BytesIO
import json
import math
from PIL import Image
from jsonschema import Draft202012Validator, FormatChecker
from .config import ROOT


SPEC = json.loads(
    (ROOT / "packages/contracts/openapi.json").read_text(encoding="utf-8")
)


def validate(name: str, value):
    schema = {"$ref": f"#/components/schemas/{name}", "components": SPEC["components"]}
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def validate_result(result: dict, duration: float):
    validate("JuryResult", result)
    for event in result.get("violations", []):
        if (
            not math.isfinite(event["timecode_sec"])
            or not 0 <= event["timecode_sec"] <= duration
        ):
            raise ValueError("Evidence time outside source")
        for frame in event["evidence_frames"]:
            if (
                not math.isfinite(frame["timestamp_sec"])
                or not 0 <= frame["timestamp_sec"] <= duration
            ):
                raise ValueError("Evidence time outside source")
            raw = base64.b64decode(frame["image_base64"], validate=True)
            with Image.open(BytesIO(raw)) as image:
                if image.format != "JPEG":
                    raise ValueError("Evidence is not JPEG")
                image.verify()
