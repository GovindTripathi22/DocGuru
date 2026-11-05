"""Request middleware for limits that must run before route body parsing."""

from __future__ import annotations

import uuid

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import settings


class UploadBodyTooLarge(Exception):
    """Raised when a multipart upload exceeds its bounded request size."""


class UploadBodyLimitMiddleware:
    """Reject oversized upload bodies before Starlette parses multipart data."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/api/upload"
        ):
            await self.app(scope, receive, send)
            return

        request_id = next(
            (
                value.decode("latin-1")
                for key, value in scope.get("headers", [])
                if key.lower() == b"x-request-id"
            ),
            uuid.uuid4().hex,
        )
        # Allow multipart boundaries and small form fields in addition to the file cap.
        max_body_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024 + 1024 * 1024

        async def reject(status: int, code: str, message: str) -> None:
            response = JSONResponse(
                {
                    "error": {
                        "code": code,
                        "message": message,
                        "request_id": request_id,
                        "details": {},
                    },
                    "detail": message,
                },
                status_code=status,
                headers={"X-Request-ID": request_id},
            )
            await response(scope, receive, send)

        content_length = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"content-length"),
            None,
        )
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                await reject(400, "BAD_REQUEST", "Invalid Content-Length header.")
                return
            if declared_size < 0:
                await reject(400, "BAD_REQUEST", "Invalid Content-Length header.")
                return
            if declared_size > max_body_bytes:
                await reject(
                    413,
                    "PAYLOAD_TOO_LARGE",
                    "Uploaded file exceeds the configured size limit.",
                )
                return

        received_bytes = 0
        body_too_large = False

        async def limited_receive() -> Message:
            nonlocal received_bytes, body_too_large
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > max_body_bytes:
                    body_too_large = True
                    raise UploadBodyTooLarge
            return message

        async def guarded_send(message: Message) -> None:
            if not body_too_large:
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except UploadBodyTooLarge:
            pass
        if body_too_large:
            await reject(
                413, "PAYLOAD_TOO_LARGE", "Uploaded file exceeds the configured size limit."
            )
