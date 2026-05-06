# AI Review Orchestration

Purpose: use cheap breadth models and stronger meta-review models without
confusing AI critique with human judgment.

## Sources Checked

- DeepSeek API docs: OpenAI-compatible endpoint, `https://api.deepseek.com`,
  current model names `deepseek-v4-flash` and `deepseek-v4-pro`, 1M context,
  JSON output/tool-call support, and announced deprecation of
  `deepseek-chat`/`deepseek-reasoner` on 2026-07-24.
- DeepSeek pricing page: very low input/output prices relative to frontier
  models, with product prices explicitly subject to change.
- MARG (2024): multi-agent review generation improves coverage by distributing
  full paper text across agents and specializing comment types.
- AGENTREVIEW (EMNLP 2024): peer review outcomes are sensitive to reviewer
  bias and role dynamics; this supports dissent preservation rather than
  majority voting alone.
- DeepReview / related peer-review dialogue work: peer review benefits from
  multi-turn, long-context, role-based interactions rather than single-shot
  review.

## Model Roles

Use model names in config, but keep prompts role-based:

- `cheap_reviewer`: DeepSeek. Handles section compression, local critique,
  checklist extraction, citation-risk scan, and formatting-risk scan.
- `domain_reviewer`: stronger model. Reviews compressed evidence plus selected
  original anchors for scientific validity and field-specific judgment.
- `meta_reviewer`: strongest available model. Audits the reviewers, resolves
  conflicts, checks overclaim risk, and prepares human-facing synthesis.
- `human_editor`: final accountable judgment.

For strong-model stages (`paper_shape`, `meta_review_issues`,
`methodology_adversary`, `author_review_plan`, `author_editorial_rewrite`),
follow the **Cross-Provider Critique Architecture** rules in
`docs/review_framework.md`. In particular: cross-provider runs go through the
manual provider seam, the merge step preserves single-provider fatals via
`needs_human_decision`, and final author output must pass through
`author_editorial_rewrite` so `redact_internal_tokens` runs as the validator
gate. Do not introduce majority voting, do not bypass the rewrite stage, and
do not replace cheap fanout with strong-model calls.

## Recommended Workflow

1. **Freeze and map**: produce `frozen/manuscript.pdf`, `normalized/manuscript.md`,
   and `provenance/source_map.jsonl`.
2. **Build layered units**: create `macro/whole.md`, `chapters/chapter_*.md`,
   and `sections/section_*.md`. See `docs/layered_review_protocol.md`.
3. **Compress first**: split manuscript into units, then ask cheap reviewers to
   produce anchored summaries, claim lists, variable definitions, and suspected
   problems. No final verdict in this round.
4. **Local review**: run cheap reviewers on each unit with specialized roles:
   methods reproducibility, evidence support, remote-sensing physics, writing
   and structure, references/citation consistency.
5. **Cross-unit synthesis**: merge local findings into a small issue graph:
   claim -> evidence -> risk -> affected sections -> suggested fix.
6. **Strong meta-review**: send the issue graph plus only the necessary original
   anchors to the stronger model. Its job is not to repeat all local comments;
   it should delete weak comments, upgrade serious ones, and identify missing
   high-level issues.
7. **Dissent pass**: run a skeptical pass asking what the current review may be
   over-penalizing or under-penalizing.
8. **Human decision**: human reviewer accepts, edits, or rejects AI-generated
   comments before sending to the author.

## Prompting Rules

Prompts follow the five-layer structure from the local prompting guide:

```text
[锚点] exact file/line/page anchors
[假设] current understanding of the manuscript or section
[卡点] most likely failure mode
[边界] do not infer unsupported facts; mark missing evidence
[格式] exact JSON or Markdown output shape
```

For agentic tooling tasks, use the four-layer form:

```text
[目标]
[验收]
[硬约束]
[资源]
```

## Cost Strategy

Use DeepSeek for high-volume passes because page/section-level review is token
heavy and benefits from redundancy. Use the expensive/stronger model only after
compression, when the input is an issue graph plus a small set of original
anchors. This preserves depth where it matters while keeping routine coverage
cheap.

## Failure Modes

- Majority agreement is not verification. Multiple cheap agents can share the
  same blind spot.
- Meta-review can become overconfident if original anchors are omitted.
- A cheap model is useful for finding possible problems, but claims about
  scientific validity require evidence-grounded verification.
- Provider pricing and model names are unstable; runtime config must keep them
  outside prompts.

## Local Secret Config

DeepSeek credentials belong in:

```text
config/secrets.local.env
```

This file is ignored by Git. Do not put API keys in prompts, templates,
Markdown review reports, or KMS.

## Minimal DeepSeek Command

After a review unit exists as a Markdown file:

```bash
PYTHONPATH=src python -m review_council.cli deepseek-review-unit \
  cases/<case-id>/units/<unit>.md \
  cases/<case-id>/reviews/deepseek/<unit>.json \
  --case-id <case-id> \
  --unit-id <unit> \
  --model deepseek-v4-flash
```

Use `deepseek-v4-flash` for cheap breadth passes. Use `deepseek-v4-pro` only
when a local pass needs stronger reasoning but still should stay cheaper than
frontier meta-review.
