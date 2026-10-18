"""Network is allowed only during explicit provisioning, never service execution."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

REPO = "Qwen/Qwen3-VL-2B-Instruct"
REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination", type=Path, default=Path("models/Qwen3-VL-2B-Instruct")
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    from huggingface_hub import HfApi

    info = HfApi().model_info(REPO, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        raise RuntimeError("Revision mismatch")
    cli = Path(sys.executable).parent / ("hf.exe" if sys.platform == "win32" else "hf")
    if not args.verify_only:
        subprocess.run(
            [
                str(cli),
                "download",
                REPO,
                "--revision",
                REVISION,
                "--local-dir",
                str(args.destination),
                "--max-workers",
                "4",
            ],
            check=True,
        )
    files = []
    for file in info.siblings:
        p = args.destination / file.rfilename
        if not p.exists():
            raise RuntimeError("Incomplete model download")
        h = hashlib.sha256()
        with p.open("rb") as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                h.update(block)
        digest = h.hexdigest()
        if file.lfs and digest != file.lfs.sha256:
            raise RuntimeError("Weight checksum mismatch")
        files.append(
            {"path": file.rfilename, "size": p.stat().st_size, "sha256": digest}
        )
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
                "provisioned": True,
                "revision": REVISION,
                "files": len(files),
                "bytes": sum(f["size"] for f in files),
            }
        )
    )


if __name__ == "__main__":
    main()
