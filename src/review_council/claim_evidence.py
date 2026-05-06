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
import re
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


_TOKEN_RE = re.compile(r"[A-Za-z0-9一-鿿]+")


def _tokens(text: str) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1]


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
    anchor_confidence: str = ""
    anchor_note: str = ""
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
                    severity = issue.get("final_severity") or issue.get("proposed_severity") or "?"
                    diagnosis = (issue.get("diagnosis") or "")[:120]
                    lines.append(f"  - **{iid}** ({severity}): {diagnosis}")
                else:
                    lines.append(f"  - {iid}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return output_path


def _suggest_issue_links(claim: Claim, issues: list[dict], link_window: int) -> list[str]:
    if claim.anchor.line_start:
        return _suggest_by_anchor(claim, issues, link_window)
    return _suggest_by_similarity(claim, issues)


def _suggest_by_anchor(claim: Claim, issues: list[dict], link_window: int) -> list[str]:
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


def _suggest_by_similarity(claim: Claim, issues: list[dict], min_overlap: int = 3) -> list[str]:
    """Fallback linker for claims without line anchors.

    Uses token overlap between claim text and the issue's diagnosis/quote/
    recommendation, restricted to issues whose source_unit matches when
    `claim.source_unit` is set. Stays conservative: only links when overlap
    is meaningful and section context is consistent.
    """
    claim_tokens = _similarity_terms(claim.text)
    if len(claim_tokens) < min_overlap:
        return []
    out: list[str] = []
    claim_unit_tail = claim.source_unit.split("/")[-1] if claim.source_unit else ""
    for issue in issues:
        if claim_unit_tail and claim_unit_tail not in {"whole", "macro"} and issue.get("source_units"):
            if not any(claim_unit_tail in unit for unit in issue["source_units"]):
                continue
        text = " ".join(
            str(issue.get(k, "") or "")
            for k in ("diagnosis", "evidence_quote", "quote", "recommendation")
        )
        issue_tokens = _similarity_terms(text)
        overlap = claim_tokens & issue_tokens
        if len(overlap) >= min_overlap:
            iid = str(issue.get("id", ""))
            if iid:
                out.append(iid)
    return out


def _similarity_terms(text: str) -> set[str]:
    terms = set(_tokens(text))
    cjk = "".join(re.findall(r"[一-鿿]+", text.lower()))
    for n in (2, 3):
        for i in range(0, max(0, len(cjk) - n + 1)):
            terms.add(cjk[i : i + n])
    return {term for term in terms if len(term) > 1}


def backfill_claim_anchors(claims_path: Path, unit_path: Path) -> dict:
    """Backfill `anchor.line_start/line_end` for claims with null anchors.

    Searches the unit body for the longest matching n-gram of claim text and
    records `anchor_confidence` (high|medium|low|none) plus `anchor_note`.
    Page is left as-is (page resolution requires a source map).
    """
    if not claims_path.exists() or not unit_path.exists():
        return {"claims": 0, "backfilled": 0}

    data = _loads_json_maybe_fenced(claims_path.read_text(encoding="utf-8"))
    raw_text = unit_path.read_text(encoding="utf-8")
    body, _frontmatter_offset, fm_line_start = _strip_frontmatter(raw_text)
    body_lines = body.splitlines()

    claims = data.get("claims") or []
    backfilled = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        anchor = claim.get("anchor") or {}
        if not isinstance(anchor, dict):
            anchor = {}
        if anchor.get("line_start"):
            claim["anchor"] = {
                "page": anchor.get("page"),
                "line_start": anchor.get("line_start"),
                "line_end": anchor.get("line_end") or anchor.get("line_start"),
            }
            claim.setdefault("anchor_confidence", "high")
            continue

        text = str(claim.get("text") or "")
        match = _locate_text_in_lines(text, body_lines)
        if match is None:
            claim["anchor"] = {"page": anchor.get("page"), "line_start": None, "line_end": None}
            claim["anchor_confidence"] = "none"
            claim["anchor_note"] = "no text match in source unit"
            continue

        local_start, local_end, confidence = match
        absolute_start = local_start + 1 + fm_line_start
        absolute_end = local_end + 1 + fm_line_start
        claim["anchor"] = {
            "page": anchor.get("page"),
            "line_start": absolute_start,
            "line_end": absolute_end,
        }
        claim["anchor_confidence"] = confidence
        claim["anchor_note"] = f"text-match in {unit_path.name}"
        backfilled += 1

    claims_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"claims": len(claims), "backfilled": backfilled}


def _loads_json_maybe_fenced(text: str) -> dict:
    stripped = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if match:
        stripped = match.group(1).strip()
    return json.loads(stripped)


def _strip_frontmatter(text: str) -> tuple[str, int, int]:
    """Return (body, frontmatter_line_count, normalized_line_start_offset).

    If the unit YAML frontmatter declares `normalized_line_start: N`, treat
    that as the absolute starting line; otherwise the body lines are 1-indexed
    relative to the unit file itself.
    """
    if not text.startswith("---"):
        return text, 0, 0
    lines = text.splitlines()
    end_index = -1
    for i in range(1, min(len(lines), 80)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index < 0:
        return text, 0, 0
    fm_block = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    fm_offset = end_index + 1  # number of consumed lines
    norm_start = 0
    match = re.search(r"^normalized_line_start:\s*(\d+)", fm_block, re.MULTILINE)
    if match:
        norm_start = int(match.group(1)) - 1  # convert to 0-based offset relative to body line 1
    return body, fm_offset, norm_start


def _locate_text_in_lines(text: str, lines: list[str]) -> tuple[int, int, str] | None:
    """Locate `text` inside `lines`. Returns (start_idx, end_idx, confidence).

    Strategy: try long n-gram match (>=8 tokens) → high; fall back to >=4 →
    medium; fall back to >=2 contiguous tokens → low. Indices are 0-based.
    """
    tokens = _tokens(text)
    if not tokens:
        return None
    haystack = "\n".join(lines)
    haystack_lower = haystack.lower()

    for n, conf in ((8, "high"), (4, "medium"), (2, "low")):
        if len(tokens) < n:
            continue
        for start in range(0, len(tokens) - n + 1):
            window = tokens[start : start + n]
            needle = " ".join(window)
            if needle in haystack_lower:
                # Find which line range it spans.
                pos = haystack_lower.find(needle)
                line_start = haystack_lower.count("\n", 0, pos)
                end_pos = pos + len(needle)
                line_end = haystack_lower.count("\n", 0, end_pos)
                return line_start, line_end, conf
        # Only return the highest-confidence match found at this level
    return None


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
        anchor_confidence=str(raw.get("anchor_confidence", "")),
        anchor_note=str(raw.get("anchor_note", "")),
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
