"""Package XML fingerprinting with canonicalization (C14N) and component separation (VAL-02)."""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile
from lxml import etree
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Volatile attribute namespaces and names stripped during C14N canonicalization
VOLATILE_ATTR_PREFIXES = (
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rsid",
)
VOLATILE_ATTR_NAMES = {
    "{http://schemas.microsoft.com/office/word/2010/wordml}paraId",
    "{http://schemas.microsoft.com/office/word/2010/wordml}textId",
}
VOLATILE_TAGS = {
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}proofErr",
}


def canonicalize_xml(xml_bytes: bytes, strip_volatile_tags: bool = True) -> bytes:
    """
    Parses XML, drops volatile attributes and proofErr elements, strips whitespace text nodes,
    and returns deterministic C14N canonical XML bytes.
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True, strip_cdata=False)
        tree = etree.fromstring(xml_bytes, parser=parser)

        # Remove volatile tags like proofErr
        if strip_volatile_tags:
            for elem in list(tree.iter()):
                if elem.tag in VOLATILE_TAGS:
                    parent = elem.getparent()
                    if parent is not None:
                        parent.remove(elem)
                        continue

                # Strip volatile attributes
                to_remove = []
                for attr in elem.attrib:
                    if any(attr.startswith(pfx) for pfx in VOLATILE_ATTR_PREFIXES) or attr in VOLATILE_ATTR_NAMES:
                        to_remove.append(attr)
                for attr in to_remove:
                    del elem.attrib[attr]

        return etree.tostring(tree, method="c14n", exclusive=True, with_comments=False)
    except Exception as e:
        logger.debug("XML canonicalization fallback to raw bytes: %s", e)
        return xml_bytes


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PackageFingerprint(BaseModel):
    components: Dict[str, str] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)
    style_hash: str = ""


def fingerprint_package(package_path: str | Path) -> PackageFingerprint:
    """
    Generates deterministic, canonical SHA-256 fingerprints for each structural OpenXML component.
    """
    path = Path(package_path)
    if not path.exists():
        return PackageFingerprint()

    ext = path.suffix.lower()
    doc_type = "docx" if ext == ".docx" else ("pptx" if ext == ".pptx" else "unknown")

    components: Dict[str, str] = {}
    details: Dict[str, Any] = {}

    try:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = set(zf.namelist())

            if doc_type == "docx":
                # 1. Styles
                if "word/styles.xml" in namelist:
                    c14n_styles = canonicalize_xml(zf.read("word/styles.xml"))
                    components["styles"] = hash_bytes(c14n_styles)
                    # Extract docDefaults
                    try:
                        parser = etree.XMLParser(remove_blank_text=True)
                        st_tree = etree.fromstring(c14n_styles, parser=parser)
                        doc_defs = st_tree.xpath("//*[local-name()='docDefaults']")
                        if doc_defs:
                            components["doc_defaults"] = hash_bytes(etree.tostring(doc_defs[0], method="c14n"))
                    except Exception:
                        pass

                # 2. Numbering
                if "word/numbering.xml" in namelist:
                    components["numbering"] = hash_bytes(canonicalize_xml(zf.read("word/numbering.xml")))

                # 3. Theme
                theme_parts = sorted([n for n in namelist if n.startswith("word/theme/") and n.endswith(".xml")])
                theme_bytes = b"".join(canonicalize_xml(zf.read(tp)) for tp in theme_parts)
                if theme_bytes:
                    components["theme"] = hash_bytes(theme_bytes)

                # 4. Font Table
                if "word/fontTable.xml" in namelist:
                    components["font_table"] = hash_bytes(canonicalize_xml(zf.read("word/fontTable.xml")))

                # 5. Settings compat
                if "word/settings.xml" in namelist:
                    raw_settings = zf.read("word/settings.xml")
                    try:
                        parser = etree.XMLParser(remove_blank_text=True)
                        tree = etree.fromstring(raw_settings, parser=parser)
                        # Remove non-layout volatile settings (rsids, updateFields, zoom)
                        for elem in list(tree.iter()):
                            lname = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                            if lname in ("rsids", "updateFields", "zoom", "proofState"):
                                parent = elem.getparent()
                                if parent is not None:
                                    parent.remove(elem)
                        components["settings_compat"] = hash_bytes(etree.tostring(tree, method="c14n"))
                    except Exception:
                        components["settings_compat"] = hash_bytes(canonicalize_xml(raw_settings))

                # 6. Page setup (sectPr in document order)
                if "word/document.xml" in namelist:
                    try:
                        parser = etree.XMLParser(remove_blank_text=True)
                        doc_tree = etree.fromstring(zf.read("word/document.xml"), parser=parser)
                        sect_prs = doc_tree.xpath("//*[local-name()='sectPr']")
                        page_setup_bytes = b"".join(canonicalize_xml(etree.tostring(sp)) for sp in sect_prs)
                        if page_setup_bytes:
                            components["page_setup"] = hash_bytes(page_setup_bytes)
                    except Exception as e:
                        logger.debug("Failed to extract page_setup: %s", e)

                # 7. Headers & Footers
                hf_parts = sorted([n for n in namelist if (n.startswith("word/header") or n.startswith("word/footer")) and n.endswith(".xml")])
                hf_bytes = b"".join(canonicalize_xml(zf.read(hp)) for hp in hf_parts)
                if hf_bytes:
                    components["headers_footers"] = hash_bytes(hf_bytes)

            elif doc_type == "pptx":
                # 1. Slide Size
                if "ppt/presentation.xml" in namelist:
                    try:
                        parser = etree.XMLParser(remove_blank_text=True)
                        pres_tree = etree.fromstring(zf.read("ppt/presentation.xml"), parser=parser)
                        sz_elems = pres_tree.xpath("//*[local-name()='sldSz' or local-name()='notesSz']")
                        sz_bytes = b"".join(canonicalize_xml(etree.tostring(e)) for e in sz_elems)
                        if sz_bytes:
                            components["slide_size"] = hash_bytes(sz_bytes)
                    except Exception:
                        pass

                # 2. Masters
                master_parts = sorted([n for n in namelist if n.startswith("ppt/slideMasters/") and n.endswith(".xml")])
                m_bytes = b"".join(canonicalize_xml(zf.read(p)) for p in master_parts)
                if m_bytes:
                    components["masters"] = hash_bytes(m_bytes)

                # 3. Layouts
                layout_parts = sorted([n for n in namelist if n.startswith("ppt/slideLayouts/") and n.endswith(".xml")])
                l_bytes = b"".join(canonicalize_xml(zf.read(p)) for p in layout_parts)
                if l_bytes:
                    components["layouts"] = hash_bytes(l_bytes)

                # 4. Themes
                theme_parts = sorted([n for n in namelist if n.startswith("ppt/theme/") and n.endswith(".xml")])
                t_bytes = b"".join(canonicalize_xml(zf.read(p)) for p in theme_parts)
                if t_bytes:
                    components["themes"] = hash_bytes(t_bytes)

                # 5. Notes / Handout Masters
                nm_parts = sorted([n for n in namelist if n.startswith("ppt/notesMasters/") or n.startswith("ppt/handoutMasters/")])
                if nm_parts:
                    nm_bytes = b"".join(canonicalize_xml(zf.read(p)) for p in nm_parts)
                    components["notes_master"] = hash_bytes(nm_bytes)

        # Style hash: first 16 chars of hash over all component values in sorted component key order
        all_hashes = "".join(components[k] for k in sorted(components.keys()))
        style_hash = hash_bytes(all_hashes.encode("utf-8"))[:16] if all_hashes else ""

        return PackageFingerprint(
            components=components,
            details=details,
            style_hash=style_hash,
        )
    except Exception as e:
        logger.warning("Failed to fingerprint package %s: %s", package_path, e)
        return PackageFingerprint()


def compute_package_fingerprint(package_path: str | Path, doc_type: Optional[str] = None) -> str:
    """Legacy shim returning 64-char or 16-char style hash."""
    fp = fingerprint_package(package_path)
    return fp.style_hash
