"""Aggregate per-unit DeepSeek reviews into a case-level issue graph.

The aggregator does not silently merge or rank issues. It produces:

- a flat list of normalized issues with stable ids;
- candidate clusters keyed by `(anchor_window, dimension, type)`;
- an empty `human_decisions` block reserved for meta-review and human edits.

Merging, dropping, and severity changes are decisions, not aggregations. Those
land in `human_decisions` after meta-review or human review.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from review_council.rubrics import DIMENSIONS

CLUSTER_WINDOW = 20

ISSUE_STATUS = (
    "raised",
    "kept",
    "dropped",
    "merged",
    "upgraded",
    "downgraded",
    "needs_human",
)


@dataclass
class IssueAnchor:
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class Issue:
    id: str
    source_units: list[str]
    anchor: IssueAnchor
    dimension: str
    type: str
    proposed_severity: str
    confirmed_severity: str = ""
    status: str = "raised"
    evidence_quote: str = ""
    diagnosis: str = ""
    recommendation: str = ""
    triggered_check_ids: list[str] = field(default_factory=list)
    raised_by: list[str] = field(default_factory=list)
    merged_into: str | None = None
    merge_children: list[str] = field(default_factory=list)
    needs_human_check: bool = False


def aggregate(deepseek_dir: Path, output_path: Path, case_id: str = "") -> dict:
    issues: list[Issue] = []
    counter = 1
    for path in sorted(deepseek_dir.rglob("*.json")):
        if path.name.startswith("._"):
            continue
        payload = _safe_load_json(path)
        if not isinstance(payload, dict):
            continue
        unit_id = str(payload.get("unit_id") or path.stem)
        layer = str(payload.get("layer") or path.parent.name)
        raised_by = f"deepseek/{layer}/{unit_id}"
        for raw in payload.get("issues", []) or []:
            if not isinstance(raw, dict):
                continue
            issue_id = f"ISS-{counter:04d}"
            counter += 1
            issues.append(
                Issue(
                    id=issue_id,
                    source_units=[f"{layer}/{unit_id}"],
                    anchor=_parse_anchor(raw),
                    dimension=_normalize_dimension(raw),
                    type=str(raw.get("type", "")),
                    proposed_severity=str(raw.get("severity", "")),
                    evidence_quote=str(raw.get("quote", "")),
                    diagnosis=str(raw.get("diagnosis", "")),
                    recommendation=str(raw.get("recommendation", "")),
                    triggered_check_ids=_as_str_list(raw.get("triggered_check_ids")),
                    raised_by=[raised_by],
                    needs_human_check=bool(raw.get("needs_human_check", False)),
                )
            )

    clusters = _cluster(issues)
    graph = {
        "case_id": case_id or deepseek_dir.parent.parent.name,
        "issues": [_serialize(i) for i in issues],
        "clusters": clusters,
        "human_decisions": [],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return graph


def _serialize(issue: Issue) -> dict:
    out = asdict(issue)
    out["anchor"] = asdict(issue.anchor)
    return out


def _safe_load_json(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    text = _strip_code_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    first_newline = stripped.find("\n")
    if first_newline < 0:
        return text
    body = stripped[first_newline + 1 :]
    if body.endswith("```"):
        body = body[: -3]
    return body.rstrip()


_LEGACY_ANCHOR_RE = re.compile(r"(?:line|L)[_\s]*(\d+)(?:\s*[-_]\s*(\d+))?", re.IGNORECASE)


def _parse_anchor(raw: dict) -> IssueAnchor:
    anchor = raw.get("anchor")
    if isinstance(anchor, dict):
        return IssueAnchor(
            page=_coerce_int(anchor.get("page")),
            line_start=_coerce_int(anchor.get("line_start")),
            line_end=_coerce_int(anchor.get("line_end")),
        )
    if isinstance(anchor, str):
        match = _LEGACY_ANCHOR_RE.search(anchor)
        if match:
            start = _coerce_int(match.group(1))
            end = _coerce_int(match.group(2)) or start
            return IssueAnchor(line_start=start, line_end=end)
    return IssueAnchor()


def _normalize_dimension(raw: dict) -> str:
    value = str(raw.get("dimension", "")).strip().lower()
    if value in DIMENSIONS:
        return value
    legacy = str(raw.get("type", "")).strip().lower()
    legacy_map = {
        "concept": "significance",
        "structure": "coherence",
        "method": "methodology",
        "evidence": "evidence",
        "validation": "evidence",
        "remote_sensing": "methodology",
        "writing": "clarity",
        "citation": "integrity",
        "format": "clarity",
    }
    return legacy_map.get(legacy, "")


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return []


def _coerce_int(value: object) -> int | None:
    try:
        if value in (None, "", "null"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _cluster(issues: Iterable[Issue]) -> list[dict]:
    buckets: dict[str, list[str]] = {}
    for issue in issues:
        key = _cluster_key(issue)
        buckets.setdefault(key, []).append(issue.id)
    return [
        {"key": key, "members": members}
        for key, members in sorted(buckets.items())
        if len(members) > 1
    ]


def _cluster_key(issue: Issue) -> str:
    line_start = issue.anchor.line_start or 0
    window = (line_start // CLUSTER_WINDOW) * CLUSTER_WINDOW
    return f"L{window:05d}|{issue.dimension or '_'}|{issue.type or '_'}"
