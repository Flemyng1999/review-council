"""Shared ingestion types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestionResult:
    source: Path
    normalized: Path | None
    warnings: list[str]
