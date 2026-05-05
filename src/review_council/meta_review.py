"""Strong-model meta-review of an issue graph.

This is the "GPT 元审稿" step in the v1 manual workflow, encoded as an
explicit stage. Reads the issue graph, the cheap-synthesized draft, and
optional claim/evidence matrix; calls a strong reasoning model with
`templates/prompts/meta_reviewer.md`; emits two artifacts:

- `reviews/meta_review.md` — narrative synthesis (Keep / Drop / Upgrade /
  Missing) for human-reviewer onboarding.
- `comments/review_comments.json` — structured author-facing comments after
  cross-anchor dedup, severity recalibration, macro re-contextualization,
  and track assignment.

The cheap `synthesize-comments` stage feeds this as the candidate-set
starting frame; this stage is the one that produces author-version quality.
"""

from __future__ import annotations

import json
from pathlib import Path

from review_council.prompts import render_prompt_template
from review_council.providers.deepseek import DEFAULT_BASE_URL, DeepSeekRequest, chat_completion

META_DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_TOP_N = 80

SEVERITY_ORDER = {"blocking": 0, "major": 1, "moderate": 2, "minor": 3}


def run_meta_review(
    *,
    issue_graph_path: Path,
    output_review_md: Path,
    output_comments_json: Path,
    prompt_template: Path,
    api_key: str,
    draft_path: Path | None = None,
    claim_matrix_path: Path | None = None,
    units_root: Path | None = None,
    model: str = META_DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    top_n_issues: int = DEFAULT_TOP_N,
) -> dict:
    graph = json.loads(issue_graph_path.read_text(encoding="utf-8"))
    issues = graph.get("issues", []) or []
    sorted_issues = sorted(
        issues,
        key=lambda issue: (
            SEVERITY_ORDER.get(
                str(issue.get("confirmed_severity") or issue.get("proposed_severity") or ""),
                99,
            ),
            (issue.get("anchor") or {}).get("line_start") or 0,
        ),
    )[:top_n_issues]

    context: dict = {
        "case_id": graph.get("case_id", ""),
        "issue_graph": {
            "issues": sorted_issues,
            "clusters": graph.get("clusters", []) or [],
        },
    }
    if draft_path and draft_path.exists():
        context["draft_comments"] = json.loads(draft_path.read_text(encoding="utf-8"))
    if claim_matrix_path and claim_matrix_path.exists():
        context["claim_matrix"] = json.loads(claim_matrix_path.read_text(encoding="utf-8"))

    prompt = render_prompt_template(prompt_template, {})
    prompt = (
        prompt.rstrip()
        + "\n\n[Supplied issue graph and context]\n```json\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + "\n```\n"
    )

    response = chat_completion(
        DeepSeekRequest(
            api_key=api_key,
            prompt=prompt,
            model=model,
            base_url=base_url,
            temperature=0.2,
        )
    )

    narrative, comments_json = split_meta_review_response(response)

    output_review_md.parent.mkdir(parents=True, exist_ok=True)
    output_review_md.write_text(narrative.rstrip() + "\n", encoding="utf-8")

    output_comments_json.parent.mkdir(parents=True, exist_ok=True)
    output_comments_json.write_text(comments_json.rstrip() + "\n", encoding="utf-8")

    parsed_comments = json.loads(comments_json) if comments_json.strip() else []
    enriched = 0
    if isinstance(parsed_comments, list) and parsed_comments:
        enriched = backfill_anchors(parsed_comments, issues, units_root=units_root)
        output_comments_json.write_text(
            json.dumps(parsed_comments, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return {
        "input_issues": len(issues),
        "considered_issues": len(sorted_issues),
        "output_comments": len(parsed_comments) if isinstance(parsed_comments, list) else 0,
        "anchors_backfilled": enriched,
        "review_md": str(output_review_md),
        "comments_json": str(output_comments_json),
    }


def backfill_anchors(
    comments: list[dict],
    issues: list[dict],
    *,
    units_root: Path | None = None,
) -> int:
    """For each comment with null line/page, copy from the first available ISS anchor.

    Falls back to the source_unit's normalized_line_start when the ISS itself has
    no specific anchor (chapter-level reviews often have no line anchor).
    Returns the number of comments enriched.
    """

    issue_index = {issue.get("id"): issue for issue in issues if issue.get("id")}
    unit_starts = _index_unit_starts(units_root) if units_root else {}

    enriched = 0
    for comment in comments:
        if comment.get("line_start") and comment.get("page"):
            continue
        for issue_id in comment.get("derived_from_issues") or []:
            issue = issue_index.get(issue_id)
            if not issue:
                continue
            anchor = issue.get("anchor") or {}
            line_start = anchor.get("line_start")
            line_end = anchor.get("line_end")
            page = anchor.get("page")
            if line_start is None:
                for unit_id in issue.get("source_units") or []:
                    if unit_id in unit_starts:
                        line_start = unit_starts[unit_id]
                        break
            if comment.get("line_start") is None and line_start is not None:
                comment["line_start"] = line_start
                if comment.get("line_end") is None:
                    comment["line_end"] = line_end or line_start
                enriched += 1
            if comment.get("page") is None and page is not None:
                comment["page"] = page
            if comment.get("line_start") and comment.get("page"):
                break
    return enriched


def _index_unit_starts(units_root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not units_root.is_dir():
        return out
    for path in units_root.rglob("*.md"):
        if path.name.startswith("._") or path.name == "index.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---", 4)
        if end < 0:
            continue
        front = text[4:end]
        line_start: int | None = None
        for raw in front.splitlines():
            if raw.startswith("normalized_line_start:"):
                value = raw.partition(":")[2].strip()
                try:
                    line_start = int(value)
                except ValueError:
                    pass
                break
        if line_start is None:
            continue
        unit_id = f"{path.parent.name}/{path.stem}"
        out[unit_id] = line_start
    return out


def split_meta_review_response(text: str) -> tuple[str, str]:
    """Split the model output into a Markdown narrative and a JSON block."""

    fence_index = text.find("```json")
    if fence_index < 0:
        fence_index = text.find("```")
        if fence_index < 0:
            raise ValueError("Meta-review response missing fenced JSON block")
        offset = 3
    else:
        offset = len("```json")

    narrative = text[:fence_index].rstrip()
    rest = text[fence_index + offset :]
    if rest.startswith("\n"):
        rest = rest[1:]

    end = rest.find("```")
    if end < 0:
        raise ValueError("Meta-review response missing closing ``` for JSON block")
    comments_json = rest[:end].strip()
    return narrative, comments_json
