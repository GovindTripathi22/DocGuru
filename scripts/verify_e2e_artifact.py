"""Reopen an end-to-end generated DOCX and confirm it contains body text."""

import sys
from pathlib import Path

from docx import Document


def main() -> None:
    artifact = Path(sys.argv[1])
    document = Document(artifact)
    body = "\n".join(paragraph.text for paragraph in document.paragraphs)
    if not body.strip():
        raise SystemExit("Generated DOCX reopened, but it contains no paragraph text.")
    print(f"Reopened generated DOCX with {len(body.split())} words.")


if __name__ == "__main__":
    main()
