"""Exercise the public real service with newly generated synthetic footage only."""

import argparse
from io import BytesIO
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
import zipfile

import httpx
from cashproof.contracts import validate_result
from synthetic_clip import create


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--credentials-file", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (
        url.scheme != "https"
        or url.username
        or url.password
        or url.path not in {"", "/"}
        or url.query
        or url.fragment
    ):
        raise ValueError(
            "Use the explicitly authorized HTTPS origin, without redirects"
        )
    credentials = json.loads(args.credentials_file.read_text(encoding="utf-8"))
    args.work_dir.mkdir(parents=True, exist_ok=False)
    source = create(args.work_dir / "CashProof-Synthetic-Test.mov", rotated=True)
    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=30,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        health = client.get("/health/ready")
        assert health.status_code == 200
        assert health.json() == {
            "ready": True,
            "mode": "server",
            "contract_version": "1.0.0",
        }
        assert client.get("/api/ui/cases").status_code == 401
        operator_headers = {"X-API-Key": credentials["operator"]}
        jury_headers = {"X-API-Key": credentials["jury"]}
        listing = client.get("/api/ui/cases", headers=operator_headers)
        assert listing.status_code == 200
        assert "no-store" in listing.headers.get("cache-control", "")
        assert client.get("/api/ui/cases", headers=jury_headers).status_code in {
            401,
            403,
        }
        started = time.monotonic()
        with source.open("rb") as stream:
            upload = client.post(
                "/api/v1/analyze",
                headers=jury_headers,
                files={"file": (source.name, stream, "video/quicktime")},
            )
        assert upload.status_code == 202
        admission = time.monotonic() - started
        job_id = upload.json()["job_id"]
        assert len(job_id) == 32 and all(c in "0123456789abcdef" for c in job_id)
        while time.monotonic() - started < 300:
            response = client.get(f"/api/v1/jobs/{job_id}", headers=jury_headers)
            assert response.status_code == 200
            result = response.json()
            if result["status"] != "processing":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Public synthetic analysis exceeded 300 seconds")
        assert result["status"] == "done", "Public synthetic job failed"
        total = time.monotonic() - started
        assert total < 300
        validate_result(result, 4.01)
        detail = client.get(f"/api/ui/cases/{job_id}", headers=operator_headers)
        assert detail.status_code == 200
        archive = client.get(f"/api/ui/cases/{job_id}/bundle", headers=operator_headers)
        assert archive.status_code == 200
        assert archive.headers.get("content-type", "").startswith("application/zip")
        assert "no-store" in archive.headers.get("cache-control", "")
        with zipfile.ZipFile(BytesIO(archive.content)) as bundle:
            assert bundle.testzip() is None
            entry_count = len(bundle.namelist())
        receipt = {
            "base_url": args.base_url,
            "health": health.json(),
            "anonymous_access_rejected": True,
            "operator_authenticated": True,
            "jury_ui_access_rejected": True,
            "new_synthetic_analysis_completed": True,
            "inference": "Real qualified local model; generated FFmpeg input only",
            "job_id": job_id,
            "upload_bytes": source.stat().st_size,
            "admission_sec": admission,
            "upload_to_result_sec": total,
            "verdict": result["verdict"],
            "event_count": len(result["violations"]),
            "ui_detail_accessible": True,
            "export_zip_entries": entry_count,
            "export_zip_bytes": len(archive.content),
            "export_crc_verified": True,
            "api_cache_control": listing.headers.get("cache-control"),
            "api_vercel_cache": listing.headers.get("x-vercel-cache"),
            "export_cache_control": archive.headers.get("cache-control"),
            "private_footage_used": False,
            "recognition_accuracy_qualified": False,
            "independent_client_network_verified": False,
        }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
