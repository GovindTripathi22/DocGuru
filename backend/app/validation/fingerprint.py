"""Package XML fingerprinting with canonicalization and volatile attribute stripping (Phase 3, VAL-01)."""

import hashlib
import io
import logging
from pathlib import Path
import re
from typing import Optional, Set
import zipfile
from lxml import etree

logger = logging.getLogger(__name__)

# Volatile attribute namespaces and local names to strip during fingerprinting
VOLATILE_ATTR_PREFIXES = ("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rsid",)
VOLATILE_ATTR_NAMES = {
    "{http://schemas.microsoft.com/office/word/2010/wordml}paraId",
    "{http://schemas.microsoft.com/office/word/2010/wordml}textId",
}

DOCX_TEMPLATE_PARTS = [
    "word/styles.xml",
    "word/settings.xml",
    "word/fontTable.xml",
    "word/theme/theme1.xml",
]

PPTX_TEMPLATE_PARTS = [
    "ppt/presentation.xml",
    "ppt/viewProps.xml",
]


def _normalize_xml(xml_bytes: bytes) -> bytes:
    """Parses XML, strips volatile attributes, and outputs canonical XML (C14N)."""
    try:
        parser = etree.XMLParser(remove_blank_text=True, strip_cdata=False)
        tree = etree.fromstring(xml_bytes, parser=parser)

        for elem in tree.iter():
            # Strip volatile attributes
            to_remove = []
            for attr in elem.attrib:
                if any(attr.startswith(pfx) for pfx in VOLATILE_ATTR_PREFIXES) or attr in VOLATILE_ATTR_NAMES:
                    to_remove.append(attr)
            for attr in to_remove:
                del elem.attrib[attr]

        # Return C14N canonical representation
        return etree.tostring(tree, method="c14n", exclusive=True, with_comments=False)
    except Exception as e:
        logger.debug("XML normalization failed, falling back to raw bytes: %s", e)
        return xml_bytes


def compute_package_fingerprint(package_path: str | Path, doc_type: Optional[str] = None) -> str:
    """
    Computes a deterministic 64-char SHA-256 fingerprint for DOCX or PPTX template package components.
    Strips volatile attributes before hashing to ensure zero-drift verification is stable.
    """
    path = Path(package_path)
    if not path.exists():
        return ""

    if doc_type is None:
        doc_type = "docx" if path.suffix.lower() == ".docx" else ("pptx" if path.suffix.lower() == ".pptx" else "unknown")

    hasher = hashlib.sha256()

    try:
        with zipfile.ZipFile(path, "r") as zf:
            file_names = sorted(zf.namelist())
            relevant_parts = []
            if doc_type == "docx":
                relevant_parts = [n for n in file_names if n in DOCX_TEMPLATE_PARTS or n.startswith("word/theme/")]
            elif doc_type == "pptx":
                relevant_parts = [
                    n for n in file_names
                    if n in PPTX_TEMPLATE_PARTS or n.startswith("ppt/slideMasters/") or n.startswith("ppt/slideLayouts/") or n.startswith("ppt/theme/")
                ]
            else:
                relevant_parts = file_names

            if not relevant_parts:
                relevant_parts = file_names

            for part_name in sorted(relevant_parts):
                try:
                    data = zf.read(part_name)
                    if part_name.endswith(".xml"):
                        norm_data = _normalize_xml(data)
                    else:
                        norm_data = data
                    hasher.update(part_name.encode("utf-8"))
                    hasher.update(norm_data)
                except KeyError:
                    continue
        return hasher.hexdigest()
    except Exception as e:
        logger.warning("Failed to compute package fingerprint for %s: %s", package_path, e)
        # Fallback to simple hash of file
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return ""
