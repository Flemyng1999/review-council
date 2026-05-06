"""Compose a polished author-facing review from strategic + detail layers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from review_council.detail_audit import CATEGORY_LABELS_ZH, CATEGORY_ORDER
from review_council.provenance import load_source_map


STRATEGIC_TRACKS = {
    "main_argument",
    "chapter_structure",
    "experimental_design",
    "methods",
    "results_validation",
}

TRACK_SECTION = {
    "main_argument": "一、主线与结构",
    "chapter_structure": "一、主线与结构",
    "experimental_design": "二、方法与可复现性",
    "methods": "二、方法与可复现性",
    "results_validation": "三、结果解释与证据强度",
}

SECTION_ORDER = (
    "一、主线与结构",
    "二、方法与可复现性",
    "三、结果解释与证据强度",
)

DETAIL_SECTION = "四、必须补齐的技术细节"
POLISH_SECTION = "五、格式、单位与文字问题"
POLISH_CATEGORIES = {"unit_consistency", "citation_check", "text_cleanup"}


def compose_author_review(
    *,
    paper_shape_path: Path,
    strategic_comments_path: Path,
    detail_audit_path: Path,
    source_map_path: Path,
    output_md_path: Path,
    output_json_path: Path | None = None,
) -> dict:
    strategic = _load_json_list(strategic_comments_path)
    detail_payload = json.loads(detail_audit_path.read_text(encoding="utf-8"))
    detail_items = [item for item in detail_payload.get("items", []) if isinstance(item, dict)]
    source_map = load_source_map(source_map_path)
    line_to_page = _line_to_page(source_map)

    review_package = {
        "revision_goals": _extract_revision_goals(paper_shape_path),
        "strategic_comments": [_normalize_strategic(c, line_to_page) for c in strategic],
        "detail_items": [_normalize_detail(item, line_to_page) for item in detail_items],
    }
    if output_json_path:
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(
            json.dumps(review_package, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    text = render_author_review_package(review_package)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(text, encoding="utf-8")
    return {
        "revision_goals": len(review_package["revision_goals"]),
        "strategic_comments": len(review_package["strategic_comments"]),
        "detail_items": len(review_package["detail_items"]),
        "output": str(output_md_path),
    }


def polish_author_review(input_md_path: Path, output_md_path: Path) -> dict:
    text = input_md_path.read_text(encoding="utf-8")
    polished = clean_author_text(text)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(polished, encoding="utf-8")
    return {"output": str(output_md_path), "chars": len(polished)}


def render_author_review_package(package: dict) -> str:
    lines: list[str] = ["# 审稿意见", ""]
    goals = package.get("revision_goals") or []
    if goals:
        lines.extend(["## 总体修改方向", ""])
        for index, goal in enumerate(goals[:3], start=1):
            lines.append(f"{index}. {clean_author_text(str(goal))}")
        lines.append("")

    strategic = [c for c in package.get("strategic_comments", []) if c.get("comment")]
    by_section: dict[str, list[dict]] = {section: [] for section in SECTION_ORDER}
    for comment in strategic:
        section = TRACK_SECTION.get(str(comment.get("track", "")))
        if not section:
            continue
        by_section.setdefault(section, []).append(comment)

    counter = 0
    for section in SECTION_ORDER:
        comments = by_section.get(section) or []
        if not comments:
            continue
        lines.extend([f"## {section}", ""])
        for comment in sorted(comments, key=_comment_sort_key):
            counter += 1
            lines.extend(_render_comment(counter, comment))

    detail_items = package.get("detail_items") or []
    required = [item for item in detail_items if item.get("category") not in POLISH_CATEGORIES]
    polish = [item for item in detail_items if item.get("category") in POLISH_CATEGORIES]
    if required:
        lines.extend([f"## {DETAIL_SECTION}", ""])
        lines.extend(_render_detail_items(required))
    if polish:
        lines.extend([f"## {POLISH_SECTION}", ""])
        lines.extend(_render_detail_items(polish))
    return clean_author_text("\n".join(lines).rstrip() + "\n")


def clean_author_text(text: str) -> str:
    replacements = [
        (r"(?:ISS|CLM|CMT)-\d{4}", ""),
        (r"[A-Z]{3,5}-\d{2,4}", ""),
        (r"\b[Pp]aper[_ -]?shape\s+[Tt]ransformation [Aa]ction\s+\d+\b", "相应总体修改方向"),
        (r"\b[Tt]ransformation [Aa]ction\s+\d+\b", "相应总体修改方向"),
        (r"\b[Pp]aper[_ -]?shape best-version insight\b", "总体修改方向"),
        (r"\b[Pp]aper[_ -]?shape\b", "总体修改方向"),
        (r"\bcheap reviewers raised multiple issues\b", "局部审查中发现多处问题"),
        (r"\bcheap reviewers\b", "局部审查"),
        (r"\bDeepSeek\b", "模型审查"),
        (r"\bmeta-review\b", "综合审查"),
        (r"\bissue graph\b", "问题清单"),
        (r"\bblocking\b", "优先修改"),
        (r"\bmajor\b", "重点修改"),
        (r"\bmoderate\b", "建议修改"),
        (r"\bminor\b", "细节修改"),
    ]
    cleaned = text
    for pattern, value in replacements:
        cleaned = re.sub(pattern, value, cleaned)
    cleaned = re.sub(r"\(\s*(?:,\s*)*\)", "", cleaned)
    cleaned = cleaned.replace("相应总体修改方向 from 总体修改方向", "相应总体修改方向")
    cleaned = cleaned.replace("Per 相应总体修改方向:", "按照相应总体修改方向，")
    cleaned = cleaned.replace("The 局部审查中发现多处问题 on", "局部审查中发现")
    cleaned = cleaned.replace("( covers LUT reproducibility; this covers the PLSR side)", "")
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _extract_revision_goals(paper_shape_path: Path) -> list[str]:
    if not paper_shape_path.exists():
        return []
    text = paper_shape_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if "Transformation" in line or "修改方向" in line:
            start = i + 1
            break
    if start < 0:
        return []
    goals: list[str] = []
    current: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("## ") and current:
            break
        if re.match(r"^\d+\.\s+", stripped):
            if current:
                goals.append(" ".join(current).strip())
            current = [re.sub(r"^\d+\.\s+", "", stripped)]
        elif current and stripped:
            current.append(stripped)
    if current:
        goals.append(" ".join(current).strip())
    return goals[:3]


def _normalize_strategic(comment: dict, line_to_page: list[tuple[int, int]]) -> dict:
    out = dict(comment)
    out["comment"] = clean_author_text(str(out.get("comment", "")))
    out["recommendation"] = clean_author_text(str(out.get("recommendation", "")))
    out["quote"] = clean_author_text(str(out.get("quote", "")))
    if not out.get("page"):
        out["page"] = _resolve_page(line_to_page, _coerce_int(out.get("line_start")))
    return out


def _normalize_detail(item: dict, line_to_page: list[tuple[int, int]]) -> dict:
    out = dict(item)
    anchor = dict(out.get("anchor") or {})
    if not anchor.get("page"):
        anchor["page"] = _resolve_page(line_to_page, _coerce_int(anchor.get("line_start")))
    out["anchor"] = anchor
    out["text"] = clean_author_text(str(out.get("text", "")))
    out["recommendation"] = clean_author_text(str(out.get("recommendation", "")))
    out["quote"] = clean_author_text(str(out.get("quote", "")))
    return out


def _render_comment(counter: int, comment: dict) -> list[str]:
    lines = [f"### {counter}. {_priority_label(comment.get('revision_priority'))} - {_format_location(comment)}", ""]
    quote = str(comment.get("quote") or "").strip()
    if quote:
        lines.extend(["> " + quote.replace("\n", "\n> "), ""])
    lines.extend([str(comment.get("comment", "")).strip(), ""])
    recommendation = str(comment.get("recommendation") or "").strip()
    if recommendation:
        lines.extend([f"建议：{recommendation}", ""])
    return lines


def _render_detail_items(items: Iterable[dict]) -> list[str]:
    lines: list[str] = []
    grouped: dict[str, list[dict]] = {}
    for item in sorted(items, key=_detail_sort_key):
        grouped.setdefault(str(item.get("category", "")), []).append(item)
    for category in sorted(grouped, key=lambda c: CATEGORY_ORDER.get(c, 99)):
        label = CATEGORY_LABELS_ZH.get(category, category)
        lines.append(f"### {label}")
        lines.append("")
        for item in grouped[category]:
            text = str(item.get("text") or "").strip()
            recommendation = str(item.get("recommendation") or "").strip()
            location = _format_location(item.get("anchor") or {})
            if recommendation and recommendation != text:
                lines.append(f"- **{location}** {text} 建议：{recommendation}")
            else:
                lines.append(f"- **{location}** {text}")
        lines.append("")
    return lines


def _format_location(obj: dict) -> str:
    anchor = obj.get("anchor") if isinstance(obj.get("anchor"), dict) else obj
    page = anchor.get("page") or obj.get("page") or "?"
    line_start = anchor.get("line_start") or obj.get("line_start")
    line_end = anchor.get("line_end") or obj.get("line_end")
    if line_start and line_end and line_start != line_end:
        return f"p. {page}, lines {line_start}-{line_end}"
    if line_start:
        return f"p. {page}, line {line_start}"
    return f"p. {page}"


def _priority_label(priority: object) -> str:
    return {"high": "优先修改", "medium": "建议修改", "low": "最后统一检查"}.get(str(priority), "建议修改")


def _comment_sort_key(comment: dict) -> tuple[int, int, int]:
    priority = {"high": 0, "medium": 1, "low": 2}.get(str(comment.get("revision_priority")), 9)
    severity = {"blocking": 0, "major": 1, "moderate": 2, "minor": 3}.get(str(comment.get("final_severity")), 9)
    return (priority, severity, _coerce_int(comment.get("line_start")) or 0)


def _detail_sort_key(item: dict) -> tuple[int, int, int]:
    priority = {"high": 0, "medium": 1, "low": 2}.get(str(item.get("priority")), 9)
    anchor = item.get("anchor") or {}
    return (CATEGORY_ORDER.get(str(item.get("category")), 99), priority, _coerce_int(anchor.get("line_start")) or 0)


def _line_to_page(source_map: dict[str, dict[str, object]]) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for record in source_map.values():
        line = _coerce_int(record.get("normalized_line_start"))
        page = _coerce_int(record.get("source_page"))
        if line is not None and page is not None:
            points.append((line, page))
    return sorted(points)


def _resolve_page(line_to_page: list[tuple[int, int]], line: int | None) -> int | None:
    if line is None or not line_to_page:
        return None
    page = None
    for point_line, point_page in line_to_page:
        if point_line > line:
            break
        page = point_page
    return page


def _load_json_list(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON list: {path}")
    return [item for item in data if isinstance(item, dict)]


def _coerce_int(value: object) -> int | None:
    try:
        if value in (None, "", "null"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
