"""Provision the pinned official 4B experiment; no private input is read."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import requests
from huggingface_hub import HfApi

REPO = "Qwen/Qwen3-VL-4B-Instruct"
REVISION = "ebb281ec70b05090aa6165b016eac8ec08e71b17"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    info = HfApi().model_info(REPO, revision=REVISION, files_metadata=True)
    if info.sha != REVISION or info.card_data.get("license") != "apache-2.0":
        raise ValueError("Unexpected official checkpoint metadata")

    def provision(file):
        target = args.destination / file.rfilename
        if not target.resolve().is_relative_to(args.destination.resolve()):
            raise ValueError("Unsafe artifact path")
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{file.rfilename}"
        if file.lfs and not target.exists():
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("resume_download.py")),
                    "--url",
                    url,
                    "--partial",
                    str(target.with_suffix(target.suffix + ".partial")),
                    "--destination",
                    str(target),
                    "--size",
                    str(file.size),
                    "--sha256",
                    file.lfs.sha256,
                    "--workers",
                    "16",
                ],
                check=True,
            )
        elif not target.exists():
            response = requests.get(url, timeout=(30, 90))
            response.raise_for_status()
            target.write_bytes(response.content)
        digest = hashlib.sha256()
        with target.open("rb") as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(block)
        if target.stat().st_size != file.size or (
            file.lfs and digest.hexdigest() != file.lfs.sha256
        ):
            raise ValueError("Candidate artifact checksum/size mismatch")
        if not file.lfs:
            blob = target.read_bytes()
            if (
                hashlib.sha1(
                    b"blob " + str(len(blob)).encode() + b"\0" + blob
                ).hexdigest()
                != file.blob_id
            ):
                raise ValueError("Candidate Git blob checksum mismatch")
        return {"path": file.rfilename, "size": file.size, "sha256": digest.hexdigest()}

    with ThreadPoolExecutor(max_workers=2) as pool:
        files = list(pool.map(provision, info.siblings))
    manifest = {
        "repo_id": REPO,
        "revision": REVISION,
        "license": "Apache-2.0",
        "source_url": f"https://huggingface.co/{REPO}/tree/{REVISION}",
        "files": files,
    }
    (args.destination / "cashproof-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "candidate_provisioned": True,
                "revision": REVISION,
                "files": len(files),
                "bytes": sum(f["size"] for f in files),
            }
        )
    )


if __name__ == "__main__":
    main()
