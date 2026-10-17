import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile


def test_portable_archive_and_checksum_support_unicode_folder_names(tmp_path):
    bundle = tmp_path / "сборка с пробелами"
    bundle.mkdir()
    payload = b"Synthetic release integrity fixture"
    (bundle / "original.bin").write_bytes(payload)
    (bundle / "manifest.json").write_text(
        json.dumps({"files": {"original.bin": hashlib.sha256(payload).hexdigest()}}),
        encoding="utf-8",
    )
    tool = Path(__file__).resolve().parents[3] / "tools/verify_bundle.py"
    result = subprocess.run(
        [sys.executable, str(tool), "--bundle", str(bundle), "--archive"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    receipt = json.loads(result.stdout)
    archive = Path(receipt["archive"])
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert receipt["archive_sha256"] == digest
    assert archive.with_suffix(".zip.sha256").read_text(encoding="utf-8") == (
        digest + "  " + archive.name + "\n"
    )
    with ZipFile(archive) as stream:
        assert stream.testzip() is None
        assert stream.read("original.bin") == payload
        assert set(stream.namelist()) == {"original.bin", "manifest.json"}
