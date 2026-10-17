"""Read-only notice inventory for a private bundle; never grants release approval."""

import argparse
from collections import Counter
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import re


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def audit(root):
    root = root.resolve(strict=True)
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    expected = manifest["files"]
    checked = {}

    def check(path):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Notice path escapes the bundle")
        relative = resolved.relative_to(root).as_posix()
        if relative in checked:
            return checked[relative]
        exists = resolved.is_file()
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest() if exists else None
        record = {
            "path": relative,
            "exists": exists,
            "sha256": digest,
            "manifest_match": exists and expected.get(relative) == digest,
        }
        checked[relative] = record
        return record

    inventory_path = root / "licenses/python-packages.json"
    check(inventory_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory_map = {normalized(item["name"]): item for item in inventory}
    site = root / "python/Lib/site-packages"
    packages = []
    for package in sorted(
        distributions(path=[str(site)]), key=lambda p: p.name.lower()
    ):
        name = package.name
        recorded = inventory_map.get(normalized(name))
        notices = []
        metadata_files = []
        for file in package.files or []:
            if Path(str(file)).name in {"METADATA", "PKG-INFO"}:
                metadata_files.append(check(package.locate_file(file)))
            if "license" in str(file).lower() or "notice" in str(file).lower():
                notices.append(check(package.locate_file(file)))
        expression = package.metadata.get("License-Expression")
        declaration = package.metadata.get("License")
        packages.append(
            {
                "name": name,
                "version": package.version,
                "inventory_version_match": bool(
                    recorded and recorded["version"] == package.version
                ),
                "license_expression": expression,
                "license_field_present": bool(declaration),
                "license_classifiers": [
                    value
                    for value in package.metadata.get_all("Classifier", [])
                    if value.startswith("License ::")
                ],
                "metadata": metadata_files,
                "notice_files": notices,
            }
        )
    required = [
        check(root / name)
        for name in (
            "python/LICENSE.txt",
            "licenses/README.txt",
            "licenses/ffmpeg-LICENSE",
            "licenses/ffmpeg-README.txt",
            "licenses/ffmpeg-provenance.json",
        )
    ]
    model_dir = root / "models" / manifest["model"]["repo_id"].split("/")[-1]
    model_card = check(model_dir / "README.md")
    model_license_files = [
        check(path)
        for path in model_dir.iterdir()
        if path.is_file()
        and path.name.lower().split(".")[0] in {"license", "notice", "copying"}
    ]
    supplemental = []
    supplemental_manifest = root / "licenses/supplemental/provenance.json"
    if supplemental_manifest.is_file():
        check(supplemental_manifest)
        supplemental = json.loads(supplemental_manifest.read_text(encoding="utf-8"))[
            "files"
        ]
        for item in supplemental:
            record = check(supplemental_manifest.parent / item["path"])
            if record["sha256"] != item["sha256"]:
                raise ValueError("Supplemental notice provenance mismatch")
    package_names = Counter(normalized(package["name"]) for package in packages)
    missing_notices = [p["name"] for p in packages if not p["notice_files"]]
    result = {
        "bundle_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_commit": manifest["source_commit"],
        "read_only": True,
        "public_redistribution_reviewed": False,
        "bundle_declares_redistribution_reviewed": manifest[
            "public_redistribution_reviewed"
        ],
        "packages": packages,
        "required_notice_files": required,
        "model_card": model_card,
        "model_standalone_license_files": model_license_files,
        "supplemental_notices": supplemental,
        "summary": {
            "package_count": len(packages),
            "inventory_count": len(inventory),
            "inventory_exact_match": (
                all(p["inventory_version_match"] for p in packages)
                and set(package_names) == set(inventory_map)
                and all(count == 1 for count in package_names.values())
            ),
            "notice_files_checked": len(checked),
            "missing_or_changed_files": sum(
                not value["manifest_match"] for value in checked.values()
            ),
            "packages_without_recorded_notice_files": missing_notices,
            "standalone_model_license_present": bool(model_license_files),
        },
        "remaining_review": [
            "FFmpeg GPLv3 corresponding source, external static libraries and build scripts",
            "PyAV embedded FFmpeg libraries and their exact sources/build details",
            "Torch/CUDA and other bundled native library redistribution terms",
            "Model license text/notices and application license declaration",
            "B-owned Electron/JavaScript distribution and user-facing third-party notices",
        ],
        "interpretation": (
            "File presence and hashes are inventory evidence only. "
            "No license compatibility or public redistribution approval is inferred."
        ),
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.resolve().is_relative_to(args.bundle.resolve()):
        raise ValueError("Preserve the immutable bundle; save the receipt outside it")
    result = audit(args.bundle)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result["summary"]))
    if (
        not result["summary"]["inventory_exact_match"]
        or result["summary"]["missing_or_changed_files"]
    ):
        raise SystemExit("Notice inventory integrity did not pass; review the receipt")


if __name__ == "__main__":
    main()
