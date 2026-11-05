from .analyze import router as analyze_router
from .download import router as download_router
from .generate import router as generate_router
from .upload import router as upload_router
from .validate import router as validate_router

__all__ = [
    "analyze_router",
    "download_router",
    "generate_router",
    "upload_router",
    "validate_router",
]
