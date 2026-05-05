"""PDF-to-Markdown page provenance helpers."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from review_council.provenance import SourceAnchor


def build_pdf_page_map(markdown_path: Path, pdf_path: Path, output_path: Path) -> list[SourceAnchor]:
    """Create Markdown line anchors enriched with frozen-PDF page numbers.

    The mapper intentionally keeps Markdown line numbers as the stable line
    anchor. PDF page-local line coordinates require layout extraction quality
    that varies heavily across DOCX renderers. Page numbers are inferred by
    matching normalized Markdown lines against extracted PDF page text, then
    filling unmapped gaps monotonically.
    """

    page_texts = _extract_pdf_page_text(pdf_path)
    page_norms = [_normalize_text(text) for text in page_texts]
    markdown_lines = markdown_path.read_text(encoding="utf-8").splitlines()

    raw_hits: dict[int, int] = {}
    last_hit_page = 1
    for line_number, line in enumerate(markdown_lines, start=1):
        needle = _normalize_markdown_line(line)
        if len(needle) < 8:
            continue
        search_order = list(range(last_hit_page, len(page_norms) + 1)) + list(range(1, last_hit_page))
        for page_index in search_order:
            page_text = page_norms[page_index - 1]
            if needle in page_text:
                raw_hits[line_number] = page_index
                if page_index >= last_hit_page:
                    last_hit_page = page_index
                break

    anchors: list[SourceAnchor] = []
    last_page: int | None = None
    next_hits = sorted(raw_hits.items())
    next_index = 0

    for line_number, line in enumerate(markdown_lines, start=1):
        if not line.strip():
            continue

        if line_number in raw_hits:
            page = raw_hits[line_number]
            last_page = page
        else:
            while next_index < len(next_hits) and next_hits[next_index][0] <= line_number:
                next_index += 1
            next_page = next_hits[next_index][1] if next_index < len(next_hits) else None
            page = last_page or next_page

        anchors.append(
            SourceAnchor(
                anchor_id=f"L{line_number:05d}",
                normalized_path=str(markdown_path),
                normalized_line_start=line_number,
                normalized_line_end=line_number,
                source_path=str(pdf_path),
                source_page=page,
                text=line.strip(),
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for anchor in anchors:
            handle.write(json.dumps(asdict(anchor), ensure_ascii=False) + "\n")
    return anchors


def _extract_pdf_page_text(pdf_path: Path) -> list[str]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("PDF page mapping requires PyMuPDF (`fitz`).") from exc

    doc = fitz.open(pdf_path)
    try:
        return [page.get_text("text") for page in doc]
    finally:
        doc.close()


def _normalize_markdown_line(line: str) -> str:
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
    line = re.sub(r"\[[^\]]*\]\([^)]*\)", "", line)
    line = re.sub(r"`([^`]*)`", r"\1", line)
    line = re.sub(r"<sup>.*?</sup>", "", line)
    line = re.sub(r"^[#>\-\*\s\d\.\)（）]+", "", line)
    return _normalize_text(line)


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[`*_#~>\-\[\]\(\)（）{}<>《》，,。.;；:：!?！？\"'“”‘’]", "", text)
    return text
