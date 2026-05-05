"""Freeze editable manuscript sources into stable review PDFs.

The canonical DOCX-to-PDF route is **manual export from Microsoft Word**.
The function below uses LibreOffice/soffice as a fallback only and renders
equations less reliably than Word's export. Prefer the manual Word route
for any case whose review depends on equation fidelity.
See `docs/paper_ingestion_protocol.md`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def freeze_docx_to_pdf(docx_path: Path, output_pdf: Path) -> Path:
    """Render a DOCX to PDF with LibreOffice/soffice as a fallback.

    Prefer exporting to PDF from Microsoft Word and placing the file at
    `cases/<case-id>/frozen/manuscript.pdf` directly. This LibreOffice path
    exists only for environments without Word; equation rendering quality is
    weaker.
    """

    print(
        "WARN: freeze-docx uses LibreOffice; equation rendering is weaker than "
        "Word's PDF export. See docs/paper_ingestion_protocol.md.",
        file=sys.stderr,
    )

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("DOCX freezing requires LibreOffice/soffice on PATH.")

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_pdf.parent
    subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp_dir),
            str(docx_path),
        ],
        check=True,
    )

    generated = temp_dir / f"{docx_path.stem}.pdf"
    if generated != output_pdf:
        generated.replace(output_pdf)
    if not output_pdf.exists():
        raise RuntimeError(f"Expected frozen PDF was not created: {output_pdf}")
    return output_pdf
