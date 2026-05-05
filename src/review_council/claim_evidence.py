"""Claim / evidence matrix as a first-class JSON artifact.

The matrix tracks author claims (CLM-####), the evidence anchors offered for
each, and the cross-references to review issues (ISS-####). The canonical
file is `evidence/claim_evidence_matrix.json`; a Markdown rendering exists
for human reading.

Boundaries:

- The aggregator (`reviews/issue_graph.json`) is rebuilt from scratch on each
  run. It does not store `linked_claims` — that would be lost on re-aggregation.
- Cross-references live in the claim matrix (`claim.linked_issues`), which is
  the human-maintained artifact.
- The linker is a heuristic helper that suggests links by anchor proximity.
  Final link decisions stay with the human reviewer.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

CLAIM_TYPES = ("method", "result", "conclusion", "interpretation", "background")
EVIDENCE_TYPES = ("data", "figure", "table", "equation", "citation", "argument")
STRENGTHS = ("strong", "moderate", "weak", "unsupported", "contradicted")

DEFAULT_LINK_WINDOW = 30


@dataclass
class ClaimAnchor:
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class EvidenceAnchor:
    type: str = ""
    ref: str = ""
    strength: str = ""
    uncertainty_note: str = ""


@dataclass
class Claim:
    id: str
    text: str
    type: str = ""
    source_unit: str = ""
    anchor: ClaimAnchor = field(default_factory=ClaimAnchor)
    evidence_anchors: list[EvidenceAnchor] = field(default_factory=list)
    linked_issues: list[str] = field(default_factory=list)


def load_claim_matrix(path: Path) -> tuple[str, list[Claim]]:
    if not path.exists():
        return "", []
    data = json.loads(path.read_text(encoding="utf-8"))
    claims = [_parse_claim(raw) for raw in data.get("claims", []) if isinstance(raw, dict)]
    return str(data.get("case_id", "")), claims


def save_claim_matrix(path: Path, case_id: str, claims: Iterable[Claim]) -> None:
    payload = {
        "case_id": case_id,
        "claims": [_serialize_claim(c) for c in claims],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def link_issues_to_claims(
    claim_matrix_path: Path,
    issue_graph_path: Path,
    *,
    link_window: int = DEFAULT_LINK_WINDOW,
    overwrite: bool = False,
) -> dict[str, int]:
    case_id, claims = load_claim_matrix(claim_matrix_path)
    if not claims or not issue_graph_path.exists():
        return {"claims": len(claims), "links_added": 0}

    issues = json.loads(issue_graph_path.read_text(encoding="utf-8")).get("issues", [])
    added = 0
    for claim in claims:
        previous = list(claim.linked_issues) if not overwrite else []
        suggested = _suggest_issue_links(claim, issues, link_window)
        merged = sorted(set(previous + suggested))
        if merged != previous:
            added += len(merged) - len(previous)
        claim.linked_issues = merged

    save_claim_matrix(claim_matrix_path, case_id, claims)
    return {"claims": len(claims), "links_added": added}


def render_claim_matrix_md(
    claim_matrix_path: Path,
    output_path: Path,
    issue_graph_path: Path | None = None,
) -> Path:
    case_id, claims = load_claim_matrix(claim_matrix_path)
    issue_index: dict[str, dict] = {}
    if issue_graph_path and issue_graph_path.exists():
        for issue in json.loads(issue_graph_path.read_text(encoding="utf-8")).get("issues", []):
            issue_index[str(issue.get("id", ""))] = issue

    lines: list[str] = ["# Claim / Evidence Matrix", ""]
    if case_id:
        lines.append(f"Case: `{case_id}`")
        lines.append("")
    lines.append(f"Claims tracked: {len(claims)}")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| Claim | Type | Source | Strength | Linked Issues |")
    lines.append("|---|---|---|---|---|")
    for claim in claims:
        anchor = _format_anchor(claim.anchor, claim.source_unit)
        strengths = sorted({e.strength for e in claim.evidence_anchors if e.strength}) or ["?"]
        linked = ", ".join(claim.linked_issues) or "-"
        text = claim.text.replace("|", "\\|")
        if len(text) > 80:
            text = text[:77] + "..."
        lines.append(f"| **{claim.id}** {text} | {claim.type or '?'} | {anchor} | {'/'.join(strengths)} | {linked} |")
    lines.append("")

    lines.append("## Per-Claim Detail")
    lines.append("")
    for claim in claims:
        lines.append(f"### {claim.id}  ({claim.type or 'unspecified'})")
        lines.append("")
        if claim.text:
            lines.append(f"> {claim.text}")
            lines.append("")
        lines.append(f"- Source: {_format_anchor(claim.anchor, claim.source_unit)}")
        if claim.evidence_anchors:
            lines.append("- Evidence:")
            for e in claim.evidence_anchors:
                pieces = [e.type or "?", e.ref or "?", e.strength or "?"]
                if e.uncertainty_note:
                    pieces.append(e.uncertainty_note)
                lines.append(f"  - {' | '.join(pieces)}")
        if claim.linked_issues:
            lines.append("- Linked issues:")
            for iid in claim.linked_issues:
                issue = issue_index.get(iid, {})
                if issue:
                    severity = issue.get("proposed_severity") or issue.get("confirmed_severity") or "?"
                    diagnosis = (issue.get("diagnosis") or "")[:120]
                    lines.append(f"  - **{iid}** ({severity}): {diagnosis}")
                else:
                    lines.append(f"  - {iid}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output_path


def _suggest_issue_links(claim: Claim, issues: list[dict], link_window: int) -> list[str]:
    if not claim.anchor.line_start:
        return []
    c_lo = claim.anchor.line_start - link_window
    c_hi = (claim.anchor.line_end or claim.anchor.line_start) + link_window

    out: list[str] = []
    for issue in issues:
        anchor = issue.get("anchor") or {}
        if not isinstance(anchor, dict):
            continue
        i_start = anchor.get("line_start")
        if not i_start:
            continue
        i_end = anchor.get("line_end") or i_start
        if i_end < c_lo or i_start > c_hi:
            continue
        if claim.source_unit and issue.get("source_units"):
            if not any(claim.source_unit.endswith(unit.split("/")[-1]) for unit in issue["source_units"]):
                continue
        out.append(str(issue.get("id", "")))
    return [oid for oid in out if oid]


def _parse_claim(raw: dict) -> Claim:
    anchor_raw = raw.get("anchor") or {}
    anchor = ClaimAnchor(
        page=_coerce_int(anchor_raw.get("page")),
        line_start=_coerce_int(anchor_raw.get("line_start")),
        line_end=_coerce_int(anchor_raw.get("line_end")),
    )
    evidence: list[EvidenceAnchor] = []
    for ev in raw.get("evidence_anchors") or []:
        if not isinstance(ev, dict):
            continue
        evidence.append(
            EvidenceAnchor(
                type=str(ev.get("type", "")),
                ref=str(ev.get("ref", "")),
                strength=str(ev.get("strength", "")),
                uncertainty_note=str(ev.get("uncertainty_note", "")),
            )
        )
    return Claim(
        id=str(raw.get("id", "")),
        text=str(raw.get("text", "")),
        type=str(raw.get("type", "")),
        source_unit=str(raw.get("source_unit", "")),
        anchor=anchor,
        evidence_anchors=evidence,
        linked_issues=[str(x) for x in raw.get("linked_issues") or [] if str(x).strip()],
    )


def _serialize_claim(claim: Claim) -> dict:
    out = asdict(claim)
    out["anchor"] = asdict(claim.anchor)
    out["evidence_anchors"] = [asdict(e) for e in claim.evidence_anchors]
    return out


def _coerce_int(value: object) -> int | None:
    try:
        if value in (None, "", "null"):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_anchor(anchor: ClaimAnchor, source_unit: str) -> str:
    page = f"p.{anchor.page}" if anchor.page else "p.?"
    if anchor.line_start:
        end = anchor.line_end or anchor.line_start
        line = f"L{anchor.line_start}-{end}" if end != anchor.line_start else f"L{anchor.line_start}"
    else:
        line = "L?"
    unit = source_unit or "?"
    return f"{unit} {page} {line}"
