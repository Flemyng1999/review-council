"""Render author-facing review comments with page/line anchors.

When the input comments carry a `track` field, the rendered Markdown groups
them by track in a fixed order (main_argument, experimental_design,
methods, results_validation, chapter_structure, references_format). When
no comment has a `track` field, the renderer falls back to a flat numbered
list — matching the original behavior for backward compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

from review_council.provenance import load_source_map

TRACK_ORDER = (
    "main_argument",
    "experimental_design",
    "methods",
    "results_validation",
    "chapter_structure",
    "references_format",
)

TRACK_LABELS = {
    "main_argument": "Main Argument",
    "experimental_design": "Experimental Design",
    "methods": "Methods",
    "results_validation": "Results & Validation",
    "chapter_structure": "Chapter Structure",
    "references_format": "References & Format",
}


def render_comments(comments_path: Path, source_map_path: Path, output_path: Path) -> None:
    comments = json.loads(comments_path.read_text(encoding="utf-8"))
    source_map = load_source_map(source_map_path)
    line_to_page = _build_line_to_page_index(source_map)

    has_tracks = any(c.get("track") for c in comments)
    if has_tracks:
        text = _render_grouped(comments, source_map, line_to_page)
    else:
        text = _render_flat(comments, source_map, line_to_page)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")


def _build_line_to_page_index(source_map: dict[str, dict[str, object]]) -> list[tuple[int, int]]:
    """Sorted list of (normalized_line_start, source_page) for line-based lookup.

    Used when a comment carries a normalized line but no anchor_id — the
    renderer scans the index to find the page of the nearest anchor at or
    before that line.
    """

    points: list[tuple[int, int]] = []
    for record in source_map.values():
        line = record.get("normalized_line_start")
        page = record.get("source_page")
        if line is None or page is None:
            continue
        try:
            points.append((int(line), int(page)))
        except (TypeError, ValueError):
            continue
    points.sort()
    return points


def _resolve_page_by_line(line_to_page: list[tuple[int, int]], line: int | None) -> int | None:
    if line is None or not line_to_page:
        return None
    import bisect

    keys = [point[0] for point in line_to_page]
    pos = bisect.bisect_right(keys, line) - 1
    if pos < 0:
        return None
    return line_to_page[pos][1]


def _render_flat(comments: list[dict], source_map: dict, line_to_page: list[tuple[int, int]]) -> str:
    lines = ["# Author-Facing Review Comments", ""]
    counter = 0
    for comment in comments:
        if not comment.get("comment"):
            continue
        counter += 1
        lines.extend(_format_comment_block(counter, comment, source_map, line_to_page))
    return "\n".join(lines).rstrip() + "\n"


def _render_grouped(comments: list[dict], source_map: dict, line_to_page: list[tuple[int, int]]) -> str:
    by_track: dict[str, list[dict]] = {}
    for comment in comments:
        if not comment.get("comment"):
            continue
        track = comment.get("track") or "_other"
        by_track.setdefault(track, []).append(comment)

    lines = ["# Author-Facing Review Comments", ""]
    track_keys = list(TRACK_ORDER) + sorted(k for k in by_track if k not in TRACK_ORDER)
    counter = 0
    for track in track_keys:
        bucket = by_track.get(track) or []
        if not bucket:
            continue
        label = TRACK_LABELS.get(track, track.replace("_", " ").title())
        lines.append(f"## {label}")
        lines.append("")
        for comment in bucket:
            counter += 1
            lines.extend(_format_comment_block(counter, comment, source_map, line_to_page))
    return "\n".join(lines).rstrip() + "\n"


def _format_comment_block(
    counter: int,
    comment: dict,
    source_map: dict,
    line_to_page: list[tuple[int, int]],
) -> list[str]:
    anchor = source_map.get(str(comment.get("anchor_id", "")), {})
    line_start = comment.get("line_start") or anchor.get("source_line_start") or anchor.get("normalized_line_start")
    line_end = comment.get("line_end") or anchor.get("source_line_end") or anchor.get("normalized_line_end")
    page = (
        comment.get("page")
        or anchor.get("source_page")
        or anchor.get("page")
        or _resolve_page_by_line(line_to_page, _coerce_int(line_start))
    )
    location = _format_location(page, line_start, line_end)

    out = [f"### {counter}. {comment.get('severity', 'comment').title()} - {location}", ""]
    quote = comment.get("quote") or anchor.get("text")
    if quote:
        out.extend(["> " + str(quote).replace("\n", "\n> "), ""])
    out.extend([str(comment["comment"]), ""])
    recommendation = comment.get("recommendation")
    if recommendation:
        out.extend([f"Recommendation: {recommendation}", ""])
    derived = comment.get("derived_from_issues") or []
    linked = comment.get("linked_claims") or []
    if derived or linked:
        provenance: list[str] = []
        if derived:
            provenance.append("from " + ", ".join(derived))
        if linked:
            provenance.append("claims " + ", ".join(linked))
        out.extend([f"_Provenance: {' · '.join(provenance)}_", ""])
    return out


def _coerce_int(value: object) -> int | None:
    try:
        if value in (None, "", "null"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_location(page: object, line_start: object, line_end: object) -> str:
    page_part = f"p. {page}" if page else "p. ?"
    if line_start and line_end and line_start != line_end:
        return f"{page_part}, normalized lines {line_start}-{line_end}"
    if line_start:
        return f"{page_part}, normalized line {line_start}"
    return page_part
