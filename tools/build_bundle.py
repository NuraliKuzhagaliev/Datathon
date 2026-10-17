"""Build an explicit portable folder. Refuse an incomplete runtime or model.

Copies are hardlinked when possible to avoid duplicate disk usage during assembly;
the resulting directory remains independent of source paths. Do not mutate it.
Archive creation is optional and requires enough free space for a full copy.
"""

import argparse
import hashlib
import json
import os
from importlib.metadata import distributions
from pathlib import Path
import shutil
import subprocess
from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def link_or_copy(source, destination):
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


def copytree(source, destination, ignore=None):
    shutil.copytree(source, destination, copy_function=link_or_copy, ignore=ignore)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--python-base", type=Path, required=True)
    p.add_argument("--site-packages", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--ffprobe", type=Path, required=True)
    p.add_argument("--ffmpeg", type=Path, required=True)
    p.add_argument("--destination", type=Path, default=ROOT / "releases/backend")
    p.add_argument("--archive", action="store_true")
    a = p.parse_args()
    manifest = json.loads(
        (a.model_dir / "cashproof-manifest.json").read_text(encoding="utf-8")
    )
    for file in manifest["files"]:
        path = a.model_dir / file["path"]
        digest = digest_file(path)
        if digest != file["sha256"]:
            raise RuntimeError("Model checksum mismatch")
    for file in [
        a.python_base / "python.exe",
        a.python_base / "python312.dll",
        a.ffmpeg,
        a.ffprobe,
        a.site_packages / "torch/__init__.py",
    ]:
        if not file.is_file():
            raise FileNotFoundError("Incomplete portable prerequisites")
    if a.destination.exists():
        raise FileExistsError("Use a new destination; existing releases are preserved")
    a.destination.mkdir(parents=True)
    py = a.destination / "python"
    py.mkdir()
    for name in [
        "python.exe",
        "pythonw.exe",
        "python3.dll",
        "python312.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "LICENSE.txt",
    ]:
        if (a.python_base / name).exists():
            link_or_copy(a.python_base / name, py / name)
    for folder in ["DLLs", "Lib"]:
        copytree(
            a.python_base / folder,
            py / folder,
            ignore=shutil.ignore_patterns(
                "site-packages", "__pycache__", "test", "idlelib", "tkinter"
            ),
        )
    copytree(
        a.site_packages,
        py / "Lib/site-packages",
        ignore=shutil.ignore_patterns(
            "__pycache__", "pip", "pip-*.dist-info", "uv", "uv-*.dist-info"
        ),
    )
    # No pyvenv.cfg or absolute .pth dependency on a development checkout is allowed.
    for file in (py / "Lib/site-packages").glob("*.pth"):
        # Editable-install paths are removed only from the copied release, never source.
        text = file.read_text(encoding="utf-8")
        if "__editable__" in text or any(
            line.strip()
            and not line.startswith("#")
            and Path(line.strip()).is_absolute()
            for line in text.splitlines()
        ):
            file.unlink()
    for file in (py / "Lib/site-packages").glob("*.dist-info/direct_url.json"):
        file.unlink()  # Development installation locations are not runtime inputs.
    copytree(
        ROOT / "services/backend/src/cashproof",
        a.destination / "app/cashproof",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    copytree(
        ROOT / "packages/contracts",
        a.destination / "packages/contracts",
        ignore=shutil.ignore_patterns("fixtures", "build_contract.py"),
    )
    copytree(ROOT / "assets/rules", a.destination / "assets/rules")
    copytree(
        a.model_dir,
        a.destination / "models/Qwen3-VL-2B-Instruct",
        ignore=shutil.ignore_patterns(".cache", ".gitattributes"),
    )
    (a.destination / "bin").mkdir()
    link_or_copy(a.ffmpeg, a.destination / "bin/ffmpeg.exe")
    link_or_copy(a.ffprobe, a.destination / "bin/ffprobe.exe")
    notices = a.destination / "licenses"
    notices.mkdir()
    for name in ["LICENSE", "LICENSE.txt", "README.txt", "provenance.json"]:
        source = a.ffmpeg.parent / name
        if source.is_file():
            link_or_copy(source, notices / ("ffmpeg-" + name))
    if not (notices / "ffmpeg-provenance.json").is_file() or not any(
        (notices / ("ffmpeg-" + name)).is_file() for name in ["LICENSE", "LICENSE.txt"]
    ):
        raise FileNotFoundError("FFmpeg provenance and license must accompany binaries")
    inventory = []
    for package in distributions(path=[str(a.site_packages)]):
        license_text = package.metadata.get(
            "License-Expression"
        ) or package.metadata.get("License")
        inventory.append(
            {
                "name": package.metadata["Name"],
                "version": package.version,
                "declared_license": license_text,
                "bundled_license_files": [
                    str(file)
                    for file in package.files or []
                    if "license" in str(file).lower() or "notice" in str(file).lower()
                ],
            }
        )
    (notices / "python-packages.json").write_text(
        json.dumps(inventory, indent=2), encoding="utf-8"
    )
    (notices / "README.txt").write_text(
        "Internal team release candidate. Python's license is python/LICENSE.txt; "
        "third-party package notices remain in python/Lib/site-packages. "
        "The Qwen model card is models/Qwen3-VL-2B-Instruct/README.md (Apache-2.0). "
        "FFmpeg license, build details and source revision are included here. "
        "A source revision link alone is not a complete corresponding-source distribution. "
        "Review FFmpeg and bundled third-party redistribution obligations before public redistribution.\n",
        encoding="utf-8",
    )
    launch = dict(
        contract_version="1.0.0",
        executable="python/python.exe",
        args_prefix=["-s"],
        cwd=".",
        env={
            "PYTHONPATH": "app",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "CASHPROOF_MODEL_DIR": "models/Qwen3-VL-2B-Instruct",
            "CASHPROOF_RULES": "assets/rules/registry.json",
            "CASHPROOF_FFMPEG": "bin/ffmpeg.exe",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
            "OTEL_SDK_DISABLED": "true",
        },
    )
    validate(
        launch,
        json.loads(
            (ROOT / "packages/contracts/desktop-launch.schema.json").read_text()
        ),
    )
    (a.destination / "launch.json").write_text(
        json.dumps(launch, indent=2), encoding="utf-8"
    )
    files = {}
    for file in a.destination.rglob("*"):
        if file.is_file():
            h = hashlib.sha256()
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    h.update(block)
            files[file.relative_to(a.destination).as_posix()] = h.hexdigest()
    (a.destination / "manifest.json").write_text(
        json.dumps(
            {
                "contract_version": "1.0.0",
                "model": manifest,
                "files": files,
                "offline_verified": False,
                "public_redistribution_reviewed": False,
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "note": "Assembly is not proof of a qualified offline launch.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "assembled": str(a.destination),
                "files": len(files),
                "offline_verified": False,
            }
        )
    )
    if a.archive:
        archive = Path(shutil.make_archive(str(a.destination), "zip", a.destination))
        h = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                h.update(block)
        archive.with_suffix(".zip.sha256").write_text(
            h.hexdigest() + "  " + archive.name + "\n"
        )


if __name__ == "__main__":
    main()
