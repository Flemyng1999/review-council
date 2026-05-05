"""TeX ingestion placeholder."""

from __future__ import annotations

from pathlib import Path

from review_council.ingest.common import IngestionResult


def ingest_tex(source: Path, normalized_dir: Path) -> IngestionResult:
    return IngestionResult(
        source=source,
        normalized=None,
        warnings=["TeX conversion is not implemented yet."],
    )
