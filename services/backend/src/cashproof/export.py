import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def bundle(detail, directory: Path):
    """No inference prompts/captions beyond the operator-visible report are exported."""
    files = {
        "report.json": json.dumps(
            detail, ensure_ascii=False, indent=2, allow_nan=False
        ).encode("utf-8")
    }
    for i, event in enumerate(detail["events"]):
        for j, frame in enumerate(event["evidence_frames"]):
            files[f"evidence/event-{i:03d}-{j}.jpg"] = base64.b64decode(
                frame["image_base64"], validate=True
            )
    for saved in detail["rules"]:
        snapshot = directory / "rule-sources" / (saved["source_sha256"] + ".txt")
        raw = snapshot.read_bytes()
        if hashlib.sha256(raw).hexdigest() != saved["source_sha256"]:
            raise ValueError("Case source snapshot hash mismatch")
        files[f"sources/{snapshot.name}"] = raw
    manifest = {
        "input_sha256": detail["input_sha256"],
        "model_version": detail["model_version"],
        "rule_registry_version": detail["rule_registry_version"],
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
        "meaning": "Hashes detect changes relative to this manifest; they do not authenticate the original scene.",
    }
    files["manifest.json"] = json.dumps(manifest, indent=2).encode()
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return out.getvalue()
