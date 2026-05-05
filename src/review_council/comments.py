"""Render author-facing review comments with page/line anchors."""

from __future__ import annotations

import json
from pathlib import Path

from review_council.provenance import load_source_map


def render_comments(comments_path: Path, source_map_path: Path, output_path: Path) -> None:
    comments = json.loads(comments_path.read_text(encoding="utf-8"))
    source_map = load_source_map(source_map_path)

    lines = ["# Author-Facing Review Comments", ""]
    for index, comment in enumerate(comments, start=1):
        if not comment.get("comment"):
            continue
        anchor = source_map.get(str(comment.get("anchor_id", "")), {})
        page = comment.get("page") or anchor.get("source_page") or anchor.get("page")
        line_start = comment.get("line_start") or anchor.get("source_line_start") or anchor.get("normalized_line_start")
        line_end = comment.get("line_end") or anchor.get("source_line_end") or anchor.get("normalized_line_end")
        location = _format_location(page, line_start, line_end)

        lines.extend(
            [
                f"## {index}. {comment.get('severity', 'comment').title()} - {location}",
                "",
            ]
        )
        quote = comment.get("quote") or anchor.get("text")
        if quote:
            lines.extend(["> " + str(quote).replace("\n", "\n> "), ""])
        lines.extend([str(comment["comment"]), ""])
        recommendation = comment.get("recommendation")
        if recommendation:
            lines.extend(["Recommendation: " + str(recommendation), ""])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _format_location(page: object, line_start: object, line_end: object) -> str:
    page_part = f"p. {page}" if page else "p. ?"
    if line_start and line_end and line_start != line_end:
        return f"{page_part}, normalized lines {line_start}-{line_end}"
    if line_start:
        return f"{page_part}, normalized line {line_start}"
    return page_part
