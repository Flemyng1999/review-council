"""DOCX ingestion placeholder.

The first implementation records the interface only. Actual conversion should
preserve comments, tables, figures, equations, and source provenance.
"""

from __future__ import annotations

from pathlib import Path

from review_council.ingest.common import IngestionResult


def ingest_docx(source: Path, normalized_dir: Path) -> IngestionResult:
    return IngestionResult(
        source=source,
        normalized=None,
        warnings=["DOCX conversion is not implemented yet."],
    )
