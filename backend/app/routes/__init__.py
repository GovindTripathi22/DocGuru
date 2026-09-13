from .upload import router as upload_router
from .analyze import router as analyze_router
from .generate import router as generate_router
from .validate import router as validate_router
from .download import router as download_router

__all__ = [
    "upload_router",
    "analyze_router",
    "generate_router",
    "validate_router",
    "download_router",
]
