"""Optional seminar template replacement preset (DOCX-03)."""

SEMINAR_PLACEHOLDERS = [
    "T i t l e",
    "Title of Seminar/Project.",
    "Title of Seminar/Project",
    "[Seminar Topic]",
    "[Title]",
    "<Title>",
    "Document Title",
    "Project Title",
    "Seminar Report On",
    "Report On",
]


def apply_seminar_preset(doc, title: str) -> None:
    """Replaces seminar-specific placeholder strings in paragraphs and tables."""
    for p in doc.paragraphs:
        for ph in SEMINAR_PLACEHOLDERS:
            if ph in p.text:
                p.text = p.text.replace(ph, title)

    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for ph in SEMINAR_PLACEHOLDERS:
                        if ph in p.text:
                            p.text = p.text.replace(ph, title)
