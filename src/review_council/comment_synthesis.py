"""Synthesize draft review_comments.json from reviews/issue_graph.json.

Heuristics:

- Keep all `blocking` and `major` severity issues unconditionally.
- For `moderate` severity, keep one per cluster (the first one encountered,
  if no higher-severity sibling already represents the cluster).
- Drop `minor` severity by default.
- Within a cluster, surface sibling issues via `derived_from_issues`.
- Order comments by severity (blocking > major > moderate) then by line.

The output is a draft. The human reviewer is expected to refine wording,
merge / split entries, and adjust severities before the comments reach the
author. This synthesizer exists to remove the mechanical part of converting
an issue graph into actionable comments, not to replace human judgment.
"""

from __future__ import annotations

import json
from pathlib import Path

SEVERITY_ORDER = {"blocking": 0, "major": 1, "moderate": 2, "minor": 3}
DEFAULT_KEEP = ("blocking", "major", "moderate")

# Hard caps applied before clustering and severity-based filtering.
# These exist because cheap reviewers (DeepSeek) tend to inflate severity
# on citation, format, and clarity-without-evidence issues. Caps are not
# the meta-review — they are the cheap pre-pass.
SEVERITY_CAPS: tuple[tuple[str, str, str], ...] = (
    # (dimension, type, max_severity)
    ("integrity", "citation", "minor"),
    ("clarity", "format", "minor"),
    ("clarity", "citation", "minor"),
    ("", "citation", "moderate"),
    ("", "format", "minor"),
)


def _apply_severity_caps(issue: dict) -> str:
    """Return the capped severity for an issue. Pure function over (dim, type, sev)."""

    raw = issue.get("confirmed_severity") or issue.get("proposed_severity") or ""
    dimension = str(issue.get("dimension", "")).strip().lower()
    issue_type = str(issue.get("type", "")).strip().lower()
    cap_order = SEVERITY_ORDER.get(raw, 99)
    for cap_dim, cap_type, cap_sev in SEVERITY_CAPS:
        if cap_dim and cap_dim != dimension:
            continue
        if cap_type and cap_type != issue_type:
            continue
        cap_value = SEVERITY_ORDER.get(cap_sev, 99)
        if cap_order < cap_value:
            cap_order = cap_value
            raw = cap_sev
    return raw


def synthesize_comments(
    issue_graph_path: Path,
    output_path: Path,
    *,
    claim_matrix_path: Path | None = None,
    keep_severities: tuple[str, ...] = DEFAULT_KEEP,
) -> dict:
    graph = json.loads(issue_graph_path.read_text(encoding="utf-8"))
    issues = graph.get("issues", []) or []
    clusters = graph.get("clusters", []) or []

    cluster_of: dict[str, tuple[str, ...]] = {}
    for cluster in clusters:
        members = tuple(sorted(cluster.get("members", []) or []))
        for member in members:
            cluster_of[member] = members

    issue_by_id = {issue["id"]: issue for issue in issues if issue.get("id")}
    keep = set(keep_severities)

    kept: list[str] = []
    seen_clusters: set[tuple[str, ...]] = set()

    capped_severity: dict[str, str] = {issue["id"]: _apply_severity_caps(issue) for issue in issues if issue.get("id")}

    for severity in ("blocking", "major", "moderate"):
        if severity not in keep:
            continue
        for issue in issues:
            sev = capped_severity.get(issue["id"], "")
            if sev != severity:
                continue
            cluster_key = cluster_of.get(issue["id"], (issue["id"],))
            if any(member in kept for member in cluster_key):
                continue
            if severity == "moderate" and cluster_key in seen_clusters:
                continue
            kept.append(issue["id"])
            seen_clusters.add(cluster_key)

    claim_link = _claim_link_index(claim_matrix_path) if claim_matrix_path else {}

    comments: list[dict] = []
    for index, issue_id in enumerate(_sort_kept(kept, issue_by_id), start=1):
        issue = issue_by_id[issue_id]
        anchor = issue.get("anchor") or {}
        siblings = list(cluster_of.get(issue_id, (issue_id,)))
        comments.append(
            {
                "id": f"CMT-{index:04d}",
                "severity": capped_severity.get(issue_id, issue.get("proposed_severity", "")),
                "anchor_id": "",
                "page": anchor.get("page"),
                "line_start": anchor.get("line_start"),
                "line_end": anchor.get("line_end"),
                "quote": issue.get("evidence_quote", ""),
                "comment": issue.get("diagnosis", ""),
                "recommendation": issue.get("recommendation", ""),
                "track": "",
                "derived_from_issues": siblings,
                "linked_claims": claim_link.get(issue_id, []),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comments, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "input_issues": len(issues),
        "kept_comments": len(comments),
        "clusters_considered": len(clusters),
    }


def _claim_link_index(claim_matrix_path: Path) -> dict[str, list[str]]:
    if not claim_matrix_path.exists():
        return {}
    data = json.loads(claim_matrix_path.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for claim in data.get("claims", []) or []:
        claim_id = str(claim.get("id", ""))
        for issue_id in claim.get("linked_issues", []) or []:
            out.setdefault(str(issue_id), []).append(claim_id)
    return out


def _sort_kept(kept: list[str], issue_by_id: dict[str, dict]) -> list[str]:
    def sort_key(issue_id: str) -> tuple[int, int]:
        issue = issue_by_id[issue_id]
        sev = SEVERITY_ORDER.get(_apply_severity_caps(issue), 99)
        anchor = issue.get("anchor") or {}
        line = anchor.get("line_start") or 0
        return (sev, line)

    return sorted(kept, key=sort_key)
