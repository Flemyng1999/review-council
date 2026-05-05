"""Provenance helpers for normalized review manuscripts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceAnchor:
    anchor_id: str
    normalized_path: str
    normalized_line_start: int
    normalized_line_end: int
    source_path: str = ""
    source_page: int | None = None
    source_line_start: int | None = None
    source_line_end: int | None = None
    text: str = ""


def build_markdown_line_map(markdown_path: Path, output_path: Path) -> list[SourceAnchor]:
    """Create one anchor per non-empty Markdown line.

    This is a fallback map. Rich importers should create block-level anchors
    from Pandoc AST, Synctex, or MinerU layout data.
    """

    anchors: list[SourceAnchor] = []
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        anchors.append(
            SourceAnchor(
                anchor_id=f"L{index:05d}",
                normalized_path=str(markdown_path),
                normalized_line_start=index,
                normalized_line_end=index,
                source_path=str(markdown_path),
                source_line_start=index,
                source_line_end=index,
                text=line.strip(),
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for anchor in anchors:
            handle.write(json.dumps(asdict(anchor), ensure_ascii=False) + "\n")
    return anchors


def load_source_map(source_map_path: Path) -> dict[str, dict[str, object]]:
    anchors: dict[str, dict[str, object]] = {}
    if not source_map_path.exists():
        return anchors
    for line in source_map_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        anchors[str(record["anchor_id"])] = record
    return anchors
