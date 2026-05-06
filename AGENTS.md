# AGENTS.md - Agent Rules for review-council

This repository builds a human-AI peer review system. Agents working here
should preserve the distinction between critique, evidence, dissent, and
human judgment.

## Cold-Start Sequence (read these BEFORE acting)

Any AI session — including the one currently reading this — must read the
following files **before** running a review workflow, executing a case,
or modifying prompts / workflow yaml / stage code. Skipping any of them
leads to predictable regressions back to single-model concatenation.

1. [`PROJECT.md`](PROJECT.md) — project type and object model.
2. [`WORKING.md`](WORKING.md) — current control panel.
3. [`docs/review_framework.md`](docs/review_framework.md) — framework
   principles. The **Cross-Provider Critique Architecture** section is a
   hard constraint, not a suggestion.
4. [`docs/ai_review_orchestration.md`](docs/ai_review_orchestration.md) —
   model roles and which stages get strong models.
5. [`docs/workflows/cold_start_review_case.md`](docs/workflows/cold_start_review_case.md) —
   the executable runbook. This translates the principles above into an
   ordered list of CLI commands and human gates for the canonical V11
   thesis_undergrad flow.
6. The case_type's workflow yaml, e.g.
   [`docs/workflows/thesis_undergrad.yaml`](docs/workflows/thesis_undergrad.yaml) —
   real stage order, real commands, real flags.

The runbook (#5) is mandatory before any case execution. The framework
doc (#3) is mandatory before any prompt or workflow modification.

## Operating Rules

- This is a **tooling project**, not a gate-controlled research project.
  Do not impose phase progress, experimental gates, daily verdict
  pressure, or "is this case finished" checkpoints unless the user
  explicitly asks for one.
- Reusable code lives under `src/review_council/`.
- Keep `scripts/` as thin command wrappers.
- Concrete manuscript review work lives under `cases/<case-id>/`.
- Reusable protocols live under `docs/`, copyable artifacts under
  `templates/`, evaluation criteria under `rubrics/`.
- Do not present AI-generated review text as final editorial judgment.
- Do not make KMS files a runtime dependency of ingestion or validation
  code.

## Author-Output Invariant

The canonical author-facing deliverable is the file produced by the
`author_editorial_rewrite` stage:

```
cases/<case-id>/comments/author_facing_comments.md
```

It is the only path that runs `redact_internal_tokens` as a final
validator (CLI exits non-zero on any leaked vendor name, internal ID,
internal severity token, or pipeline noun). **Never send any of the
following directly to the author:**

- `reviews/issue_graph.json`
- `reviews/methodology_adversary.json` / `.secondary.json` / `.merged.json` / `.merged.md`
- `comments/review_comments.meta.json`
- `comments/author_review_plan.json` / `.md`
- `comments/author_facing_comments.legacy.md` (legacy renderer output)
- `comments/supervisor_internal.md` (internal-traceability view)

`compose_author_review` and `author_polish` are **legacy / fallback
stages from the V6 era**. They still run in the workflow yaml because
`author_editorial_rewrite`'s offline branch reuses the compose body when
no strong-model API key is present. They are **not** the canonical
author deliverable. The canonical file is overwritten by
`author_editorial_rewrite` later in the pipeline.

## Cross-Provider Invariant

The methodology adversary stage runs at least primary (DeepSeek by
default) and may run a secondary via the manual provider. The merge
stage produces `reviews/methodology_adversary.merged.json`, which the
plan stage consumes. Three structural rules from
`docs/review_framework.md` are restated here because violating them
silently is the most likely AI failure mode:

- **Single-provider fatal findings must not be drowned by majority
  voting.** The merge step's `needs_human_decision` list escalates them
  for human review. Do not replace this with a vote.
- **Adversary findings must survive the plan stage.**
  `_force_merge_adversary` re-attaches dropped fatal items even after
  the strong model rewrites the plan; do not remove this.
- **Adversary findings must survive the rewrite stage.** The rewrite
  prompt's `### 隐藏假设与对照缺口` and `### 论文核心声明的证据匹配度`
  subsections are mandatory templates with explicit "禁止压平" clauses;
  do not relax them.

## Case Privacy Boundary

`cases/` is private data:

- Do not `git add cases/`. The directory is intentionally untracked.
- Do not copy case content into `README.md`, `AGENTS.md`, `PROJECT.md`,
  `WORKING.md`, `docs/`, `templates/`, or test fixtures.
- A case id (e.g. `paper_B-jmz`) may be referenced as "the N=1
  validation case in `cases/<id>/retrospective.md`", but the
  manuscript's facts, claims, numbers, or review content must not be
  reproduced outside the case directory.
- Tests must use minimal synthetic fixtures, not pasted case content.

## KMS Boundary

The repository is the review production system. KMS is the knowledge
governance system. Upgrade reusable lessons to KMS through documented
pointers rather than duplicating governance content inside the
repository.

Agents may draft KMS profile or onboarding files inside this repository.
Agents must not directly modify KMS governance files, project profiles,
or methodology cards unless the user explicitly authorizes that action
and the KMS rules allow it.

## When Not To Optimize

V11 = 8/8 on the methodology rubric is a single-case (`paper_B-jmz`)
result, validated **in principle, not in repeated practice**. Continuing
to chase higher scores on the same case is in the marginal-loss region.
The right next experiment is a clean run on a structurally different
case (different case_type, different discipline, different cultivar /
domain), not another prompt-tuning iteration on the same one.

When a fresh case is available, `docs/workflows/cold_start_review_case.md`
§3 is the runbook to follow. Do not skip the cross-provider secondary
just because primary deepseek looks good.
