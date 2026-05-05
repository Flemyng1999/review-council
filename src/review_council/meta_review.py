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
    return {
        "input_issues": len(issues),
        "considered_issues": len(sorted_issues),
        "output_comments": len(parsed_comments) if isinstance(parsed_comments, list) else 0,
        "review_md": str(output_review_md),
        "comments_json": str(output_comments_json),
    }


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
