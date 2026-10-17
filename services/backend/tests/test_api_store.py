import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
import pytest
from cashproof.contracts import validate
from cashproof.jobs import Store

OP = {"X-API-Key": "o" * 32}
JURY = {"X-API-Key": "j" * 32}


def upload(client, clip, key=OP):
    return client.post(
        "/api/v1/analyze",
        headers=key,
        files={"file": ("任意 name.MOV", clip.read_bytes(), "video/quicktime")},
    )


def test_auth_upload_and_scopes(client, clip):
    for headers in [{}, {"X-API-Key": "wrong"}]:
        response = client.post(
            "/api/v1/analyze", headers=headers, content=b"not multipart"
        )
        assert response.status_code == 401
        validate("Error", response.json())
    response = upload(client, clip, JURY)
    assert response.status_code == 202
    validate("UploadAccepted", response.json())
    job = response.json()["job_id"]
    response = client.get(f"/api/v1/jobs/{job}", headers=JURY)
    validate("JuryResult", response.json())
    assert response.json() == dict(job_id=job, status="processing")
    assert client.get("/api/ui/cases", headers=JURY).status_code == 401
    assert client.get(f"/api/v1/jobs/{job}", headers=OP).status_code == 200
    detail = client.get(f"/api/ui/cases/{job}", headers=OP).json()
    validate("CaseDetail", detail)
    validate("CaseList", client.get("/api/ui/cases", headers=OP).json())
    validate("RuleRegistry", client.get("/api/ui/rules", headers=OP).json())
    assert client.get(f"/api/ui/cases/{job}/media", headers=OP).status_code == 409
    assert client.get(f"/api/ui/cases/{job}/bundle", headers=OP).status_code == 409


def test_corrupt_wrong_field_and_oversize(client, settings):
    assert (
        client.post(
            "/api/v1/analyze", headers=OP, files={"file": ("x.MOV", b"corrupt")}
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/v1/analyze", headers=OP, files={"video": ("x.MOV", b"corrupt")}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/analyze",
            headers=OP | {"Content-Length": str(200 * 1024 * 1024)},
            content=b"x",
        ).status_code
        == 413
    )
    assert client.app.state.store.list() == []


def test_five_submissions_bounded_admission(client, clip):
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(lambda _: upload(client, clip).status_code, range(5)))
    assert statuses.count(202) == 1 and statuses.count(429) == 4
    assert len(client.app.state.store.list()) == 1


def test_duplicate_upload_distinct_jobs_and_restart(client, clip):
    a = upload(client, clip).json()["job_id"]
    store = client.app.state.store
    store.fail(a, "RESOURCE_EXHAUSTED")
    b = upload(client, clip).json()["job_id"]
    assert a != b and store.get(a)["input_sha256"] == store.get(b)["input_sha256"]
    store.recover()
    for job in [a, b]:
        result = client.get(f"/api/v1/jobs/{job}", headers=OP).json()
        validate("JuryResult", result)
        assert result["status"] == "failed" and "verdict" not in result


def test_jury_cannot_poll_operator_case_and_saturation_skips_parsing(client, clip):
    job = upload(client, clip).json()["job_id"]
    assert client.get(f"/api/v1/jobs/{job}", headers=JURY).status_code == 404
    # A saturated request is rejected before even trying to parse a malformed body.
    response = client.post("/api/v1/analyze", headers=OP, content=b"not multipart")
    assert response.status_code == 429 and response.headers["Retry-After"] == "10"


def test_review_export_original_immutable(client, clip, registry):
    from cashproof.inference.pipeline import Pipeline
    from test_media_pipeline import ScriptedSyntheticModel

    response = upload(client, clip)
    job = response.json()["job_id"]
    store = client.app.state.store
    import time

    detail, _ = Pipeline(ScriptedSyntheticModel(), registry).run(
        store.directory(job) / "input.mov",
        store.directory(job),
        job,
        time.time() + 60,
        lambda **kw: store.update(job, **kw),
    )
    store.update(job, **detail, status="done", stage="complete", progress_percent=100)
    original = client.get(f"/api/v1/jobs/{job}", headers=OP).json()
    event = detail["events"][0]["event_id"]
    response = client.put(
        f"/api/ui/cases/{job}/reviews/{event}",
        headers=OP,
        json={"decision": "dismissed", "note": "Synthetic benign explanation"},
    )
    assert response.status_code == 200
    validate("Review", response.json())
    assert client.get(f"/api/v1/jobs/{job}", headers=OP).json() == original
    result = client.get(f"/api/ui/cases/{job}", headers=OP).json()
    validate("CaseDetail", result)
    assert result["events"][0]["review"]["decision"] == "dismissed"
    response = client.get(f"/api/ui/cases/{job}/bundle", headers=OP)
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as z:
        manifest = json.loads(z.read("manifest.json"))
        assert any(n.startswith("sources/") for n in z.namelist())
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest
    with pytest.raises(ValueError):
        store.update(job, model_result=None)
    assert client.delete(f"/api/ui/cases/{job}", headers=OP).json() == {"deleted": True}
    assert client.get(f"/api/v1/jobs/{job}", headers=OP).status_code == 404


def test_health_truthful_and_no_production_stub(client):
    validate("HealthLive", client.get("/health/live").json())
    client.app.state.worker.ready = False
    response = client.get("/health/ready")
    assert response.status_code == 503
    validate("HealthReady", response.json())
    assert client.get("/docs").status_code == 404


def test_expired_queue_and_lost_worker_claim(settings):
    import time

    store = Store(settings.data_dir)
    job = store.reserve("synthetic.mov", "owner", 1, "test", "test")
    store.update(job, input_sha256="a" * 64)
    with store.connect() as db:
        db.execute("UPDATE jobs SET created=? WHERE id=?", (time.time() - 300, job))
    store.expire_queued(270)
    assert store.get(job)["error"]["code"] == "DEADLINE_EXCEEDED"
    second = store.reserve("synthetic.mov", "owner", 1, "test", "test")
    store.update(second, input_sha256="b" * 64)
    assert store.claim()[0] == second
    store.recover_claimed()
    assert store.get(second)["error"]["code"] == "WORKER_RESTARTED"


def test_contract_fixtures():
    root = Path(__file__).resolve().parents[3] / "packages/contracts/fixtures"
    for path in root.glob("*.json"):
        schema = (
            "JuryResult"
            if path.name.startswith("jury")
            else "CaseDetail"
            if path.name.startswith("ui")
            else "RuleRegistry"
        )
        validate(schema, json.loads(path.read_text(encoding="utf-8")))
