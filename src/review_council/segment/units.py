"""Build hierarchical review units from normalized Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from review_council.segment.risk import write_risk_table


@dataclass(frozen=True)
class ReviewUnit:
    unit_id: str
    layer: str
    title: str
    line_start: int
    line_end: int
    path: Path


_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


def build_hierarchical_units(markdown_path: Path, output_root: Path) -> list[ReviewUnit]:
    """Create macro, chapter, and section units for layered review."""

    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    output_root.mkdir(parents=True, exist_ok=True)
    units: list[ReviewUnit] = []

    units.append(_write_unit(output_root, "macro", "whole", "Whole Manuscript", 1, len(lines), lines))
    units.extend(_write_heading_units(output_root, "chapters", "chapter", lines, level=1))
    units.extend(_write_heading_units(output_root, "sections", "section", lines, level=2))
    _write_index(output_root, units)
    write_risk_table(output_root)
    return units


def _write_heading_units(
    output_root: Path,
    directory: str,
    layer: str,
    lines: list[str],
    level: int,
) -> list[ReviewUnit]:
    headings: list[tuple[int, str]] = []
    marker = "#" * level
    for index, line in enumerate(lines, start=1):
        match = _HEADING_RE.match(line)
        if match and match.group(1) == marker:
            headings.append((index, match.group(2).strip()))

    units: list[ReviewUnit] = []
    for position, (line_start, title) in enumerate(headings, start=1):
        line_end = headings[position][0] - 1 if position < len(headings) else len(lines)
        unit_id = f"{layer}_{position:02d}"
        units.append(_write_unit(output_root, directory, unit_id, title, line_start, line_end, lines))
    return units


def _write_unit(
    output_root: Path,
    directory: str,
    unit_id: str,
    title: str,
    line_start: int,
    line_end: int,
    lines: list[str],
) -> ReviewUnit:
    path = output_root / directory / f"{unit_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(lines[line_start - 1 : line_end]).strip()
    header = [
        "---",
        f"unit_id: {unit_id}",
        f"title: {title}",
        f"normalized_line_start: {line_start}",
        f"normalized_line_end: {line_end}",
        "---",
        "",
    ]
    path.write_text("\n".join(header) + body + "\n", encoding="utf-8")
    return ReviewUnit(unit_id=unit_id, layer=directory, title=title, line_start=line_start, line_end=line_end, path=path)


def _write_index(output_root: Path, units: list[ReviewUnit]) -> None:
    lines = ["# Review Units", ""]
    lines.append("| Unit | Layer | Lines | Title |")
    lines.append("|---|---|---:|---|")
    for unit in units:
        rel = unit.path.relative_to(output_root)
        lines.append(f"| `{rel}` | {unit.layer} | {unit.line_start}-{unit.line_end} | {unit.title} |")
    (output_root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
