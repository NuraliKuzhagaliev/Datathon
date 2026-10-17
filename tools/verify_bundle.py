"""Verify every release file, optionally making a checksummed portable ZIP."""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    root = args.bundle.resolve()
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    entries = list(manifest["files"].items())
    entries.append(("manifest.json", hashlib.sha256(manifest_bytes).hexdigest()))
    archive = Path(str(root) + ".zip")
    temporary = archive.with_suffix(".zip.partial")
    if args.archive and (archive.exists() or temporary.exists()):
        raise FileExistsError(
            "Use a new archive destination; existing outputs are preserved"
        )
    total = 0
    output = (
        ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=1, allowZip64=True)
        if args.archive
        else None
    )
    try:
        for name, expected in entries:
            path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("Unsafe or missing release manifest entry")
            digest = hashlib.sha256()
            writer = output.open(name, "w", force_zip64=True) if output else None
            try:
                with path.open("rb") as source:
                    for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                        total += len(block)
                        digest.update(block)
                        if writer:
                            writer.write(block)
            finally:
                if writer:
                    writer.close()
            if digest.hexdigest() != expected:
                raise ValueError("Release file checksum mismatch")
    finally:
        if output:
            output.close()
    result = {"files_verified": len(entries), "uncompressed_bytes": total}
    if args.archive:
        temporary.rename(archive)
        digest = hashlib.sha256()
        with archive.open("rb") as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                digest.update(block)
        archive.with_suffix(".zip.sha256").write_text(
            digest.hexdigest() + "  " + archive.name + "\n", encoding="utf-8"
        )
        result.update(
            archive=str(archive),
            archive_bytes=archive.stat().st_size,
            archive_sha256=digest.hexdigest(),
        )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
