"""Validate uploaded file signatures and package structure before analysis."""

import zipfile
from pathlib import Path, PurePosixPath

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from ..config import settings
from ..errors import UnsupportedFile

MAX_ZIP_ENTRIES = 5_000
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100


def validate_uploaded_file(path: Path, extension: str) -> None:
    """Reject malformed, encrypted, macro-enabled, or oversized document packages."""
    with path.open("rb") as source:
        signature = source.read(8)

    if extension in {".docx", ".pptx"}:
        _validate_ooxml(path, extension, signature)
    elif extension == ".pdf":
        _validate_pdf(path, signature)
    else:
        raise UnsupportedFile("Only DOCX, PPTX, and PDF files are supported.")


def _validate_ooxml(path: Path, extension: str, signature: bytes) -> None:
    if not signature.startswith(b"PK\x03\x04"):
        raise UnsupportedFile("The uploaded Office file is not a valid OOXML package.")

    required_parts = {"[Content_Types].xml"}
    required_parts.add("word/document.xml" if extension == ".docx" else "ppt/presentation.xml")
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise UnsupportedFile("The Office package contains too many entries.")
            names = {entry.filename for entry in entries}
            if not required_parts.issubset(names):
                raise UnsupportedFile("The Office package is missing required document parts.")
            if any(
                PurePosixPath(entry.filename).is_absolute()
                or ".." in PurePosixPath(entry.filename).parts
                or "\\" in entry.filename
                or "\x00" in entry.filename
                for entry in entries
            ):
                raise UnsupportedFile("The Office package contains an unsafe path.")
            if any(entry.flag_bits & 0x1 for entry in entries):
                raise UnsupportedFile("Encrypted Office packages are not supported.")
            if any(
                PurePosixPath(entry.filename.replace("\\", "/")).name.lower() == "vbaproject.bin"
                for entry in entries
            ):
                raise UnsupportedFile("Macro-enabled Office files are not supported.")
            total_uncompressed = sum(entry.file_size for entry in entries)
            total_compressed = sum(entry.compress_size for entry in entries)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise UnsupportedFile("The Office package expands beyond the allowed size.")
            ratio = total_uncompressed / max(total_compressed, 1)
            if ratio > MAX_COMPRESSION_RATIO or any(
                entry.file_size / max(entry.compress_size, 1) > MAX_COMPRESSION_RATIO
                for entry in entries
            ):
                raise UnsupportedFile("The Office package compression ratio is unsafe.")
    except zipfile.BadZipFile as exc:
        raise UnsupportedFile("The uploaded Office file is not a readable OOXML package.") from exc


def _validate_pdf(path: Path, signature: bytes) -> None:
    if not signature.startswith(b"%PDF-"):
        raise UnsupportedFile("The uploaded file does not have a valid PDF signature.")
    try:
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise UnsupportedFile("Encrypted PDF files are not supported.")
        if len(reader.pages) > settings.MAX_PDF_PAGES:
            raise UnsupportedFile(
                f"The PDF has more than the allowed {settings.MAX_PDF_PAGES} pages."
            )
    except UnsupportedFile:
        raise
    except (OSError, ValueError, PyPdfError) as exc:
        raise UnsupportedFile("The uploaded PDF could not be read.") from exc
