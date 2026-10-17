from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException


class UploadLimit:
    """Bound the HTTP body before multipart parsing can spool unlimited bytes."""

    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/v1/analyze":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = self.max_bytes + 1
        if length > self.max_bytes:
            return await JSONResponse(
                {
                    "error": {
                        "code": "UPLOAD_TOO_LARGE",
                        "message": "Upload exceeds the configured body limit.",
                    }
                },
                status_code=413,
            )(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                raise HTTPException(413, "Upload exceeds the configured body limit.")
            return message

        await self.app(scope, bounded_receive, send)
