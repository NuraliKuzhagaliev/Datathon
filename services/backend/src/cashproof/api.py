from contextlib import asynccontextmanager
import asyncio
import hashlib
import hmac
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from .config import Settings
from .errors import ProcessingError
from .jobs import Store, QueueFull, owner_id
from .rules import Registry
from .media import validate_container
from .export import bundle
from .worker import Worker
from .upload_limit import UploadLimit


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["unreviewed", "confirmed", "dismissed", "uncertain"]
    note: str = Field(max_length=2000)


def error(code, message, status, headers=None):
    return JSONResponse(
        {"error": {"code": code, "message": message}},
        status_code=status,
        headers=headers,
    )


def create_app(settings: Settings, worker=None):
    store = Store(settings.data_dir)
    registry = Registry(settings.rules_path)
    worker = worker or Worker(settings)

    @asynccontextmanager
    async def lifespan(app):
        worker.start()
        try:
            yield
        finally:
            worker.close()

    app = FastAPI(
        title="CashProof",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.store, app.state.worker = store, worker
    app.add_middleware(UploadLimit, max_bytes=settings.max_upload_bytes + 1024 * 1024)

    @app.middleware("http")
    async def access(request, call_next):
        reserved = None
        if request.url.path.startswith("/api/"):
            key = request.headers.get("X-API-Key", "")
            is_operator = hmac.compare_digest(
                key.encode(), settings.operator_key.encode()
            )
            is_jury = bool(settings.jury_key) and hmac.compare_digest(
                key.encode(), settings.jury_key.encode()
            )
            if not (is_operator or is_jury):
                return error("UNAUTHORIZED", "A valid X-API-Key is required.", 401)
            request.state.operator = is_operator
            request.state.owner = owner_id(key)
            if request.url.path.startswith("/api/ui/") and not is_operator:
                return error("UNAUTHORIZED", "An operator key is required.", 401)
            if request.method == "POST" and request.url.path == "/api/v1/analyze":
                if not worker.ready:
                    return error(
                        "WORKER_UNAVAILABLE", "Local worker/model is not ready.", 503
                    )
                try:
                    reserved = store.reserve(
                        "upload.mov",
                        request.state.owner,
                        settings.max_pending,
                        worker.model_version,
                        registry.version,
                    )
                except QueueFull:
                    return error(
                        "QUEUE_FULL",
                        "No capacity is available within the processing budget.",
                        429,
                        {"Retry-After": "10"},
                    )
                request.state.reserved_job = reserved
        try:
            response = await call_next(request)
        except BaseException:
            if reserved and store.get(reserved)["input_sha256"] is None:
                store.delete(reserved)
            raise
        if (
            reserved
            and response.status_code != 202
            and store.get(reserved)["input_sha256"] is None
        ):
            store.delete(reserved)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return error(
            "NOT_FOUND" if exc.status_code == 404 else "REQUEST_REJECTED",
            str(exc.detail),
            exc.status_code,
            exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return error(
            "INVALID_REQUEST", "The request does not match the API contract.", 422
        )

    def get(job, request):
        try:
            detail = store.get(job)
            if not request.state.operator and store.owner(job) != request.state.owner:
                raise KeyError(job)
            return detail
        except KeyError:
            raise HTTPException(404, "Case not found.") from None

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        return JSONResponse(
            dict(ready=worker.ready, mode=settings.mode, contract_version="1.0.0"),
            status_code=200 if worker.ready else 503,
        )

    @app.post("/api/v1/analyze", status_code=202)
    async def analyze(request: Request, file: UploadFile = File(...)):
        form = await request.form()
        if list(form.keys()) != ["file"] or len(form.getlist("file")) != 1:
            raise HTTPException(422, "Exactly one multipart file field is required.")
        if file.size is not None and file.size > settings.max_upload_bytes:
            raise HTTPException(413, "Upload exceeds 128 MiB.")
        job = request.state.reserved_job
        store.update(
            job,
            filename=Path((file.filename or "video.mov").replace("\\", "/")).name[:255],
        )
        path = store.directory(job) / "input.mov"
        try:
            digest = hashlib.sha256()
            size = 0
            with path.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "Upload exceeds 128 MiB.")
                    out.write(chunk)
                    digest.update(chunk)
            await asyncio.to_thread(validate_container, path)
            store.update(job, input_sha256=digest.hexdigest())
        except ProcessingError:
            raise HTTPException(
                415,
                "Expected a readable MOV/MP4 container with one H.264 video stream.",
            ) from None
        except BaseException:
            raise
        finally:
            await file.close()
        return {"job_id": job}

    @app.get("/api/v1/jobs/{job_id}")
    def jury(job_id: str, request: Request):
        detail = get(job_id, request)
        if detail["status"] == "done":
            return detail["model_result"]
        result = dict(job_id=job_id, status=detail["status"])
        if detail["status"] == "failed":
            result["error"] = detail["error"]
        return result

    @app.get("/api/ui/cases")
    def cases():
        return {
            "items": [
                {k: d[k] for k in ("job_id", "filename", "created_at", "status")}
                | {
                    "verdict": d["model_result"]["verdict"]
                    if d["model_result"]
                    else None
                }
                for d in store.list()
            ]
        }

    @app.get("/api/ui/cases/{job_id}")
    def case(job_id: str, request: Request):
        return get(job_id, request)

    @app.get("/api/ui/rules")
    def rules():
        return registry.public()

    @app.put("/api/ui/cases/{job_id}/reviews/{event_id}")
    def review(job_id: str, event_id: str, value: ReviewInput, request: Request):
        get(job_id, request)
        try:
            return store.review(job_id, event_id, value.decision, value.note)
        except KeyError:
            raise HTTPException(404, "Event not found.") from None

    @app.get("/api/ui/cases/{job_id}/media")
    def media(job_id: str, request: Request):
        detail = get(job_id, request)
        if not detail["media_ready"]:
            raise HTTPException(409, "Preview is not ready.")
        return FileResponse(
            store.directory(job_id) / "preview.mp4", media_type="video/mp4"
        )

    @app.get("/api/ui/cases/{job_id}/bundle")
    def export(job_id: str, request: Request):
        detail = get(job_id, request)
        if detail["status"] != "done":
            raise HTTPException(409, "Result is not ready.")
        return Response(
            bundle(detail, store.directory(job_id)),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="cashproof-{job_id}.zip"'
            },
        )

    @app.delete("/api/ui/cases/{job_id}")
    def delete(job_id: str, request: Request):
        detail = get(job_id, request)
        if detail["status"] == "processing":
            raise HTTPException(422, "A processing case cannot be deleted.")
        store.delete(job_id)
        return {"deleted": True}

    if settings.frontend_dir and settings.frontend_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=settings.frontend_dir, html=True),
            name="frontend",
        )
    return app
