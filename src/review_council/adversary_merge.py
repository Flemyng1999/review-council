"""Merge multiple methodology_adversary outputs into a unified view.

Cross-provider critique only matters if the merge step does the right
work: dedupe near-duplicates, classify agreement, surface single-provider
fatal findings as needs_human_decision rather than silently dropping
them, and never collapse genuine disagreement into a single chosen
answer.

The merge is text-similarity based (token Jaccard ≥ threshold) — small,
local, no external dependencies. Good enough for the small scale
(typically ≤ 4 adversary inputs per case).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_CJK_RE = re.compile(r"[一-鿿]")
DEFAULT_SIMILARITY = 0.3  # Sørensen–Dice with stopwords removed

# Generic English stopwords that produce spurious matches when the rest of
# the strings have low information overlap (e.g. test fixture texts).
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "not", "is", "are", "was", "were",
        "be", "been", "being", "of", "in", "on", "at", "to", "for", "with",
        "by", "from", "as", "this", "that", "these", "those", "it", "its",
        "if", "all", "any", "some", "more", "most", "each", "every", "such",
        "no", "yes", "do", "does", "did", "have", "has", "had",
        "finding", "found", "about", "between", "across", "into", "onto",
        "study", "studies", "paper", "papers", "result", "results",
        "shown", "demonstrated", "show", "shows",
    }
)

_SEV_ORDER = {"fatal": 0, "major": 1, "moderate": 2}


def merge_adversaries(
    input_paths: list[Path],
    output_path: Path,
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY,
    md_output_path: Path | None = None,
) -> dict:
    """Merge a list of adversary JSON files into a unified report.

    Missing input files are skipped with a notice but do not fail the
    merge. This lets workflow stages declare optional secondary
    adversaries without breaking the run when no one has dropped a
    response in yet.
    """
    sources: list[dict] = []
    runs: list[tuple[str, int, dict]] = []
    skipped: list[str] = []
    case_id = ""

    for raw_path in input_paths:
        path = Path(raw_path)
        if not path.exists():
            skipped.append(str(path))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            skipped.append(str(path))
            continue
        if not isinstance(data, dict):
            skipped.append(str(path))
            continue
        if data.get("source") in {"manual_pending", "offline_stub"}:
            skipped.append(str(path))
            continue

        if not case_id and data.get("case_id"):
            case_id = str(data["case_id"])
        provider = str(data.get("provider") or "unknown")
        sources.append({"path": str(path), "provider": provider, "model": data.get("model", "")})
        for run in _iter_runs(data):
            runs.append((provider, int(run.get("run_index") or 1), run))

    providers = sorted({p for p, _, _ in runs})
    n_total_runs = len(runs)

    flat_ha = [
        (p, r, item)
        for p, r, run in runs
        for item in (run.get("hidden_assumptions") or [])
        if isinstance(item, dict)
    ]
    flat_goals = [
        (p, r, item)
        for p, r, run in runs
        for item in (run.get("unmet_research_goals") or [])
        if isinstance(item, dict)
    ]
    flat_deps = [
        (p, r, item)
        for p, r, run in runs
        for item in (run.get("headline_claim_dependencies") or [])
        if isinstance(item, dict)
    ]

    merged_ha = _merge_hidden_assumptions(flat_ha, providers, similarity_threshold)
    merged_goals = _merge_unmet_goals(flat_goals, providers, similarity_threshold)
    merged_deps = _merge_claim_dependencies(flat_deps, providers, similarity_threshold)

    needs_human = _compute_needs_human(merged_ha, merged_goals, merged_deps)

    merged = {
        "case_id": case_id,
        "source_files": sources,
        "skipped_inputs": skipped,
        "providers": providers,
        "n_total_runs": n_total_runs,
        "hidden_assumptions": merged_ha,
        "unmet_research_goals": merged_goals,
        "headline_claim_dependencies": merged_deps,
        "needs_human_decision": needs_human,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if md_output_path is not None:
        md_output_path.parent.mkdir(parents=True, exist_ok=True)
        md_output_path.write_text(_render_md(merged), encoding="utf-8")

    return merged


# --- per-section merging ---------------------------------------------------


def _merge_hidden_assumptions(
    items: list[tuple[str, int, dict]],
    providers: list[str],
    similarity_threshold: float,
) -> list[dict]:
    groups = _group_by_text(items, "assumption", similarity_threshold)
    out: list[dict] = []
    for index, group in enumerate(groups, start=1):
        canonical = _longest(group, "assumption")
        severities = [_severity(item) for _, _, item in group]
        sev_votes = _count_votes(severities)
        agreement = _classify_agreement(group, providers, severities)
        out.append(
            {
                "id": f"MERGE-A-{index:02d}",
                "assumption": str(canonical.get("assumption") or "").strip(),
                "breakage": str(canonical.get("breakage") or "").strip(),
                "reported_check": str(canonical.get("reported_check") or "").strip(),
                "severity": _highest_severity(severities) or "major",
                "severity_votes": sev_votes,
                "agreement": agreement,
                "found_by": _found_by(group),
            }
        )
    return out


def _merge_unmet_goals(
    items: list[tuple[str, int, dict]],
    providers: list[str],
    similarity_threshold: float,
) -> list[dict]:
    groups = _group_by_text(items, "stated_goal", similarity_threshold)
    out: list[dict] = []
    for group in groups:
        canonical = _longest(group, "stated_goal")
        verdicts = [_verdict(item) for _, _, item in group]
        verdict_votes = _count_votes(verdicts)
        majority = max(verdict_votes, key=verdict_votes.get) if verdict_votes else ""
        agreement = _classify_agreement(group, providers, verdicts)
        out.append(
            {
                "stated_goal": str(canonical.get("stated_goal") or "").strip(),
                "evidence_in_paper": str(canonical.get("evidence_in_paper") or "").strip(),
                "verdict": majority,
                "verdict_votes": verdict_votes,
                "agreement": agreement,
                "found_by": _found_by(group),
            }
        )
    return out


def _merge_claim_dependencies(
    items: list[tuple[str, int, dict]],
    providers: list[str],
    similarity_threshold: float,
) -> list[dict]:
    groups = _group_by_text(items, "paper_claim", similarity_threshold)
    out: list[dict] = []
    for index, group in enumerate(groups, start=1):
        canonical = _longest(group, "paper_claim")
        severities = [_severity(item) for _, _, item in group]
        agreement = _classify_agreement(group, providers, severities)
        # Union of dependencies across the group
        dep_set: list[str] = []
        for _, _, item in group:
            for dep in item.get("depends_on_assumptions") or []:
                dep_str = str(dep)
                if dep_str and dep_str not in dep_set:
                    dep_set.append(dep_str)
        out.append(
            {
                "id": f"MERGE-HCD-{index:02d}",
                "paper_claim": str(canonical.get("paper_claim") or "").strip(),
                "depends_on_assumptions": dep_set,
                "if_violated_downgrade_to": str(canonical.get("if_violated_downgrade_to") or "").strip(),
                "severity": _highest_severity(severities) or "major",
                "severity_votes": _count_votes(severities),
                "agreement": agreement,
                "found_by": _found_by(group),
            }
        )
    return out


def _compute_needs_human(
    hidden_assumptions: list[dict],
    unmet_goals: list[dict],
    claim_deps: list[dict],
) -> list[dict]:
    out: list[dict] = []
    for ha in hidden_assumptions:
        if ha["agreement"] == "conflict":
            out.append(
                {
                    "kind": "hidden_assumption",
                    "id": ha["id"],
                    "reason": "severity disagreement across sources",
                }
            )
        elif ha["agreement"] == "single_provider_only" and ha["severity"] == "fatal":
            out.append(
                {
                    "kind": "hidden_assumption",
                    "id": ha["id"],
                    "reason": "single provider raised as fatal — confirm before dropping",
                }
            )
    for dep in claim_deps:
        # claim downgrades always escalate — they touch the paper's headline
        out.append(
            {
                "kind": "headline_claim_dependency",
                "id": dep["id"],
                "reason": "headline claim downgrade requires editorial judgment",
            }
        )
    for goal in unmet_goals:
        if goal["agreement"] == "conflict":
            out.append(
                {
                    "kind": "unmet_research_goal",
                    "stated_goal": goal["stated_goal"][:120],
                    "reason": "verdict disagreement across sources",
                }
            )
    return out


# --- text grouping primitives ---------------------------------------------


def _group_by_text(
    items: list[tuple[str, int, dict]],
    text_field: str,
    threshold: float,
) -> list[list[tuple[str, int, dict]]]:
    groups: list[list[tuple[str, int, dict]]] = []
    for item in items:
        tokens = _tokenize(str(item[2].get(text_field) or ""))
        if not tokens:
            continue
        placed = False
        for group in groups:
            ref_tokens = _tokenize(str(group[0][2].get(text_field) or ""))
            if _jaccard(tokens, ref_tokens) >= threshold:
                group.append(item)
                placed = True
                break
        if not placed:
            groups.append([item])
    return groups


def _tokenize(text: str) -> set[str]:
    """Mixed-language tokenizer.

    Latin words and numeric literals are kept as whole tokens; Chinese is
    tokenized as character bigrams. The earlier greedy regex glued whole
    Chinese phrases into one token, which made two writers describing the
    same finding share almost no tokens. Bigrams give enough granularity
    for Jaccard to detect paraphrase across providers.
    """
    out: set[str] = set()
    for tok in _LATIN_RE.findall(text):
        low = tok.lower()
        if low in _STOPWORDS:
            continue
        out.add(low)
    for tok in _NUMBER_RE.findall(text):
        out.add(tok)
    # Chinese: bigrams of consecutive CJK characters.
    run: list[str] = []
    for ch in text:
        if _CJK_RE.match(ch):
            run.append(ch)
            continue
        if len(run) >= 2:
            for i in range(len(run) - 1):
                out.add(run[i] + run[i + 1])
        elif run:
            out.add(run[0])
        run = []
    if len(run) >= 2:
        for i in range(len(run) - 1):
            out.add(run[i] + run[i + 1])
    elif run:
        out.add(run[0])
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    """Sørensen–Dice coefficient (named `_jaccard` for backward compat).

    Dice = 2|A∩B| / (|A|+|B|) is symmetric like Jaccard but less sensitive
    to size asymmetry — important when two providers describe the same
    finding at very different verbosity levels.
    """
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def _longest(group: list[tuple[str, int, dict]], field: str) -> dict:
    return max(group, key=lambda t: len(str(t[2].get(field) or "")))[2]


def _classify_agreement(
    group: list[tuple[str, int, dict]],
    all_providers: list[str],
    votes: list[str],
) -> str:
    item_providers = {p for p, _, _ in group}
    distinct_votes = {v for v in votes if v}
    if len(distinct_votes) > 1:
        return "conflict"
    if all_providers and item_providers == set(all_providers) and len(all_providers) > 1:
        return "all_agree"
    if len(item_providers) > 1:
        return "multi_provider"
    return "single_provider_only"


def _found_by(group: list[tuple[str, int, dict]]) -> list[dict]:
    out: list[dict] = []
    for provider, run_index, item in group:
        out.append(
            {
                "provider": provider,
                "run_index": run_index,
                "original_id": str(item.get("id") or ""),
            }
        )
    return out


def _severity(item: dict) -> str:
    return str(item.get("severity") or "").lower()


def _verdict(item: dict) -> str:
    return str(item.get("verdict") or "").lower()


def _count_votes(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        if not v:
            continue
        out[v] = out.get(v, 0) + 1
    return out


def _highest_severity(sevs: list[str]) -> str:
    if not sevs:
        return ""
    valid = [s for s in sevs if s in _SEV_ORDER]
    if not valid:
        return sevs[0]
    return min(valid, key=lambda s: _SEV_ORDER[s])


def _iter_runs(payload: dict) -> list[dict]:
    if isinstance(payload.get("runs"), list):
        return [r for r in payload["runs"] if isinstance(r, dict)]
    return [
        {
            "run_index": 1,
            "hidden_assumptions": payload.get("hidden_assumptions") or [],
            "unmet_research_goals": payload.get("unmet_research_goals") or [],
            "headline_claim_dependencies": payload.get("headline_claim_dependencies") or [],
        }
    ]


# --- markdown rendering ----------------------------------------------------


def _render_md(merged: dict) -> str:
    lines: list[str] = ["# Merged Methodology Adversary Findings", ""]
    providers = ", ".join(merged.get("providers") or []) or "(none)"
    lines.append(
        f"Providers: {providers} | Total runs: {merged.get('n_total_runs', 0)}"
    )
    if merged.get("skipped_inputs"):
        lines.append(f"Skipped inputs: {', '.join(merged['skipped_inputs'])}")
    lines.append("")

    needs_human = merged.get("needs_human_decision") or []
    if needs_human:
        lines.append("## Needs Human Decision")
        lines.append("")
        for nh in needs_human:
            label = nh.get("id") or nh.get("stated_goal", "?")[:60]
            lines.append(f"- **{nh.get('kind','?')}** {label} — {nh.get('reason','')}")
        lines.append("")

    lines.append("## Hidden Assumptions")
    lines.append("")
    for ha in merged.get("hidden_assumptions") or []:
        lines.append(f"### {ha['id']}  ({ha['agreement']}, {ha['severity']})")
        lines.append("")
        lines.append(ha.get("assumption", "").strip() or "(empty)")
        lines.append("")
        if ha.get("breakage"):
            lines.append(f"*Breakage*: {ha['breakage']}")
            lines.append("")
        if ha.get("reported_check"):
            lines.append(f"*Reported check*: {ha['reported_check']}")
            lines.append("")
        sources = ", ".join(
            f"{fb['provider']}#{fb['run_index']}" for fb in ha.get("found_by") or []
        )
        lines.append(f"*Found by*: {sources}")
        lines.append("")

    lines.append("## Unmet Research Goals")
    lines.append("")
    for g in merged.get("unmet_research_goals") or []:
        votes = g.get("verdict_votes") or {}
        votes_str = ", ".join(f"{k}:{v}" for k, v in votes.items()) or "(no votes)"
        lines.append(
            f"- ({g.get('agreement','?')}, verdict={g.get('verdict','?')}, {votes_str}) "
            f"{g.get('stated_goal','')}"
        )
    lines.append("")

    lines.append("## Headline Claim Dependencies")
    lines.append("")
    for dep in merged.get("headline_claim_dependencies") or []:
        lines.append(f"### {dep['id']}  ({dep['agreement']}, {dep['severity']})")
        lines.append("")
        lines.append(f"**Claim**: {dep.get('paper_claim','')}")
        lines.append("")
        deps = ", ".join(dep.get("depends_on_assumptions") or []) or "(none)"
        lines.append(f"**Depends on**: {deps}")
        lines.append("")
        lines.append(f"**Downgrade to**: {dep.get('if_violated_downgrade_to','')}")
        lines.append("")
        sources = ", ".join(
            f"{fb['provider']}#{fb['run_index']}" for fb in dep.get("found_by") or []
        )
        lines.append(f"*Found by*: {sources}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
