"""Detail-audit pass for author-review composition.

The strong meta-review is intentionally selective: it should protect the
paper's main argument from being drowned by local issues. This module keeps
the complementary artifact: a compact pool of concrete technical details
that must survive into the author-facing checklist.
"""

from __future__ import annotations

import json
from pathlib import Path


CATEGORY_LABELS_ZH = {
    "variable_definition": "变量定义与换算",
    "unit_consistency": "单位一致性",
    "method_parameter": "方法参数与可复现性",
    "data_protocol": "实验与数据协议",
    "citation_check": "文献与模型引用",
    "text_cleanup": "文字、编号与格式",
}

CATEGORY_ORDER = {
    "data_protocol": 0,
    "variable_definition": 1,
    "method_parameter": 2,
    "unit_consistency": 3,
    "citation_check": 4,
    "text_cleanup": 5,
}

DETAIL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "variable_definition",
        (
            "spad",
            "lcc",
            "cab",
            "ccc",
            "lai",
            "变量",
            "转换",
            "公式",
            "定义",
            "目标变量",
        ),
    ),
    (
        "unit_consistency",
        (
            "unit",
            "单位",
            "μg/cm",
            "ug/cm",
            "g/m",
            "rmse",
            "ccc",
            "cab",
        ),
    ),
    (
        "method_parameter",
        (
            "optimal_n",
            "n窗口",
            "窗口",
            "采样",
            "随机种子",
            "seed",
            "top-k",
            "lambda",
            "sigma",
            "λ",
            "σ",
            "sg",
            "spa",
            "snv",
            "plsr",
            "prosail",
            "prospect",
            "lut",
            "参数",
            "步长",
            "搜索",
            "反演质量",
            "不确定性",
        ),
    ),
    (
        "data_protocol",
        (
            "et",
            "sza",
            "太阳天顶角",
            "盐分",
            "水分",
            "样本数",
            "年份",
            "日期",
            "重复",
            "随机化",
            "灌溉",
            "处理组合",
            "ec",
            "ece",
        ),
    ),
    (
        "citation_check",
        (
            "citation",
            "reference",
            "引用",
            "文献",
            "参考文献",
            "prospect",
            "prosail",
            "sail",
        ),
    ),
    (
        "text_cleanup",
        (
            "format",
            "typo",
            "错字",
            "病句",
            "编号",
            "4.5",
            "4.6",
            "叶斯",
            "红外波段",
            "公式编号",
            "图表",
        ),
    ),
)

MAX_ITEMS_PER_CATEGORY = 10
DEFAULT_MAX_ITEMS = 36


def build_detail_audit(
    issue_graph_path: Path,
    output_path: Path,
    *,
    max_items: int = DEFAULT_MAX_ITEMS,
) -> dict:
    graph = json.loads(issue_graph_path.read_text(encoding="utf-8"))
    issues = graph.get("issues", []) or []

    items: list[dict] = []
    per_category: dict[str, int] = {}
    seen_keys: set[tuple[str, int | None, str]] = set()
    for issue in sorted(issues, key=_issue_sort_key):
        category = _classify_issue(issue)
        if not category:
            continue
        if per_category.get(category, 0) >= MAX_ITEMS_PER_CATEGORY:
            continue
        anchor = issue.get("anchor") or {}
        diagnosis = str(issue.get("diagnosis") or issue.get("evidence_quote") or "").strip()
        recommendation = str(issue.get("recommendation") or "").strip()
        if not diagnosis and not recommendation:
            continue
        key = (category, _coerce_int(anchor.get("line_start")), _compact_key(diagnosis or recommendation))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        per_category[category] = per_category.get(category, 0) + 1
        items.append(
            {
                "type": "checklist_item",
                "category": category,
                "category_label": CATEGORY_LABELS_ZH.get(category, category),
                "priority": _detail_priority(issue, category),
                "anchor": {
                    "page": anchor.get("page"),
                    "line_start": anchor.get("line_start"),
                    "line_end": anchor.get("line_end"),
                },
                "quote": issue.get("evidence_quote") or issue.get("quote") or "",
                "text": _detail_text(issue, category),
                "recommendation": recommendation,
                "source_issues": [str(issue.get("id", ""))] if issue.get("id") else [],
            }
        )
        if len(items) >= max_items:
            break

    payload = {
        "case_id": graph.get("case_id", ""),
        "items": items,
        "counts_by_category": {
            category: sum(1 for item in items if item["category"] == category)
            for category in CATEGORY_ORDER
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "input_issues": len(issues),
        "detail_items": len(items),
        "output": str(output_path),
    }


def _classify_issue(issue: dict) -> str:
    text = " ".join(
        str(issue.get(key, "") or "")
        for key in ("dimension", "type", "evidence_quote", "diagnosis", "recommendation")
    ).lower()
    matches: list[tuple[int, str]] = []
    for category, keywords in DETAIL_RULES:
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score:
            matches.append((score, category))
    if not matches:
        return ""
    matches.sort(key=lambda pair: (-pair[0], CATEGORY_ORDER.get(pair[1], 99)))
    return matches[0][1]


def _detail_priority(issue: dict, category: str) -> str:
    severity = str(issue.get("final_severity") or issue.get("proposed_severity") or "")
    if severity in {"blocking", "major"} and category in {"method_parameter", "data_protocol", "variable_definition"}:
        return "high"
    if severity in {"blocking", "major", "moderate"}:
        return "medium"
    return "low"


def _detail_text(issue: dict, category: str) -> str:
    diagnosis = str(issue.get("diagnosis") or "").strip()
    recommendation = str(issue.get("recommendation") or "").strip()
    if diagnosis:
        return diagnosis
    if recommendation:
        return recommendation
    return f"检查{CATEGORY_LABELS_ZH.get(category, category)}相关问题。"


def _issue_sort_key(issue: dict) -> tuple[int, int, int]:
    severity = str(issue.get("final_severity") or issue.get("proposed_severity") or "")
    severity_rank = {"blocking": 0, "major": 1, "moderate": 2, "minor": 3}.get(severity, 9)
    category = _classify_issue(issue)
    category_rank = CATEGORY_ORDER.get(category, 99)
    anchor = issue.get("anchor") or {}
    return (category_rank, severity_rank, _coerce_int(anchor.get("line_start")) or 0)


def _compact_key(text: str) -> str:
    return "".join(text.lower().split())[:100]


def _coerce_int(value: object) -> int | None:
    try:
        if value in (None, "", "null"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
