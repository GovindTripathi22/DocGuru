import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import settings
from .errors import AppError
from .routes.analyze import router as analyze_router
from .routes.download import router as download_router
from .routes.enhance import router as enhance_router
from .routes.generate import router as generate_router
from .routes.upload import router as upload_router
from .routes.validate import router as validate_router

import json
import sys

class JSONLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        for attr in ("request_id", "job_id", "method", "path", "status", "duration_ms"):
            if hasattr(record, attr):
                log_entry[attr] = getattr(record, attr)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


log_handler = logging.StreamHandler(sys.stdout)
log_handler.setFormatter(JSONLogFormatter())
root_logger = logging.getLogger()
root_logger.handlers = [log_handler]
root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger("backend")


def make_error_response(code: str, message: str, request_id: str, http_status: int, details: dict | None = None) -> JSONResponse:
    content = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or {},
        },
        "detail": message,
    }
    return JSONResponse(content, status_code=http_status, headers={"X-Request-ID": request_id})


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("startup mode=%s provider=%s model=%s", settings.mode, settings.MODEL_PROVIDER, settings.MODEL_NAME)
    yield


app = FastAPI(title=settings.APP_NAME, version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID", "X-API-Key", "X-Session-Id"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except AppError as error:
        response = make_error_response(error.code, error.message, request_id, error.http_status, error.details)
    except Exception:
        logger.exception("unhandled request failure", extra={"request_id": request_id})
        response = make_error_response("INTERNAL_ERROR", "The request could not be completed.", request_id, 500)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    return make_error_response(exc.code, exc.message, request_id, exc.http_status, exc.details)


from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 400:
        code = "BAD_REQUEST"
    elif exc.status_code == 422:
        code = "UNPROCESSABLE_ENTITY"
    elif exc.status_code == 413:
        code = "PAYLOAD_TOO_LARGE"
    if exc.headers and "X-Error-Code" in exc.headers:
        code = exc.headers["X-Error-Code"]
    return make_error_response(code, str(exc.detail), request_id, exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex)
    return make_error_response("VALIDATION_ERROR", "The request body or parameters failed validation.", request_id, 422, {"errors": exc.errors()})


for router in (upload_router, analyze_router, generate_router, validate_router, download_router, enhance_router):
    app.include_router(router)


@app.get("/health/live")
async def live_check():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready_check():
    return JSONResponse({"ready": settings.ready, "mode": settings.mode}, status_code=200 if settings.ready else 503)


@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy" if settings.ready else "degraded",
        "app_name": settings.APP_NAME,
        "version": __version__,
        "model_provider": settings.MODEL_PROVIDER,
        "model_name": settings.MODEL_NAME,
        "mode": settings.mode,
        "ready": settings.ready,
        "time": int(time.time()),
        "capabilities": {
            "images": bool(settings.UNSPLASH_ACCESS_KEY or settings.PEXELS_API_KEY),
            "preview": settings.PREVIEW_ENABLED,
            "edit_pptx": True,
            "max_upload_mb": settings.MAX_UPLOAD_MB,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
