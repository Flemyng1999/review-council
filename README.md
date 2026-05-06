# review-council
Structured human-AI peer review with evidence, dissent, and accountable judgment.

`review-council` is a human-AI peer review production system. It turns a
manuscript and its attachments into a traceable review case: source files,
normalized text, reviewable units, evidence records, role-specific reviews,
dissent, human editorial judgment, and retrospective lessons.

## Core Rule

AI may generate critique. Human reviewers own judgment.

## Cold-Start Reading

If you are an AI session or a new contributor reading this for the first time,
go through these in order **before running any review workflow or modifying
prompts**:

1. [`PROJECT.md`](PROJECT.md) — project type and object model.
2. [`AGENTS.md`](AGENTS.md) — agent rules, including the Author-Output
   Invariant and Cross-Provider Invariant.
3. [`docs/review_framework.md`](docs/review_framework.md) — the
   **Cross-Provider Critique Architecture** section is a hard constraint.
4. [`docs/workflows/cold_start_review_case.md`](docs/workflows/cold_start_review_case.md)
   — the executable runbook for a full case end-to-end.

The runbook is the single source of truth for "how to run a case." This README
covers project shape and the canonical commands.

## Repository Shape

```text
cases/<case-id>/
├── source/       # original DOCX, TeX, PDF, figures, supplements
├── frozen/       # stable PDF snapshot for author-facing page anchors
├── normalized/   # converted review-ready manuscript artifacts
├── units/        # section or claim-level review units
├── evidence/     # claim/evidence matrices and source anchors
├── reviews/      # primary, verifier, dissent, and synthesis reviews
├── decision/     # human-owned editorial judgment
└── retrospective.md
```

`cases/` is private data. Do not commit it.

Reusable code lives in `src/review_council/`; protocols live in `docs/`;
rubrics live in `rubrics/`; copyable case artifacts live in `templates/`.

## Quick Start

```bash
python -m review_council.cli init-case demo_001
python -m review_council.cli validate-case cases/demo_001
```

Inspect what a workflow will run for a given case:

```bash
python -m review_council.cli review-case cases/demo_001 --list
python -m review_council.cli list-rubrics --case-type thesis_undergrad --layer section
```

## Full V11 Thesis Review Flow

This is the canonical end-to-end command sequence for a `thesis_undergrad`
case. The deeper procedural runbook with anti-patterns, troubleshooting, and
the cross-provider sub-flow is
[`docs/workflows/cold_start_review_case.md`](docs/workflows/cold_start_review_case.md).

```bash
# 1) Initialize the case
python -m review_council.cli init-case <case-id> \
  --case-type thesis_undergrad --discipline <discipline>

# 2) Place source under cases/<case-id>/source/, then either:
#    - DOCX: open in Microsoft Word, export to PDF, save as
#            cases/<case-id>/frozen/manuscript.pdf
#    - PDF:  copy or symlink source/<file>.pdf to
#            cases/<case-id>/frozen/manuscript.pdf

# 3) Run MinerU on the GPU host
ssh ubuntu-303 -p 5422
bash scripts/mineru_case_extract.sh cases/<case-id>/frozen/manuscript.pdf cases/<case-id>

# 4) First workflow pass: every automatic stage runs; human gates print
#    instructions and stop. The cross-provider secondary stage writes a
#    manual_pending stub on this pass — that is expected.
python -m review_council.cli review-case cases/<case-id>

# 5) Cross-provider secondary (the V11 increment):
#    a) Open the cached prompt:
#         cases/<case-id>/reviews/methodology_adversary.secondary_prompt.md
#    b) Paste the entire prompt into an external LLM (Claude, ChatGPT,
#       Gemini, local model — any provider different from the primary).
#    c) Save the model's full response to:
#         cases/<case-id>/reviews/methodology_adversary.secondary_response.txt
#    d) Re-run the workflow:
python -m review_council.cli review-case cases/<case-id>
#    The secondary stage now ingests the response, the merge stage rebuilds
#    methodology_adversary.merged.json, plan re-runs, rewrite re-runs.

# 6) Inspect the canonical author deliverable
cat cases/<case-id>/comments/author_facing_comments.md

# 7) Resolve human gates: claim_matrix_review, dissent, integrity_check,
#    review_comments_human_edit, editorial_decision, retrospective. The
#    workflow yaml prints each gate's instruction.
```

DOCX → Markdown via pandoc is not supported (breaks equations). The canonical
ingestion route is `source -> frozen/manuscript.pdf -> MinerU ->
normalized/manuscript.md`. See
[docs/paper_ingestion_protocol.md](docs/paper_ingestion_protocol.md) and
[docs/MinerU使用指南.md](docs/MinerU使用指南.md).

## Canonical Author Deliverable

The file you send to the author is exactly:

```
cases/<case-id>/comments/author_facing_comments.md
```

It is produced by the `author_editorial_rewrite` stage, which runs
`redact_internal_tokens` as a final validator. **If that command exits
non-zero with `WARNING: N internal tokens leaked: ...`, the file is not
deliverable.** Investigate the leak (typically a new vendor name or
internal noun the redaction patterns do not yet cover), patch
`INTERNAL_TOKEN_PATTERNS` in `src/review_council/author_editorial.py`, and
re-run.

`compose_author_review` and `author_polish` are V6-era legacy / fallback
stages. They write to the same `comments/author_facing_comments.md` early
in the pipeline; `author_editorial_rewrite` overwrites it later. **Do not
treat `compose_author_review`'s output as final.** Do not send
`reviews/issue_graph.json`, `reviews/methodology_adversary.merged.*`,
`comments/author_review_plan.*`, `comments/author_facing_comments.legacy.md`,
or `comments/supervisor_internal.md` to the author — they leak internal
provenance and bypass the validator.

## Other Key Docs

- [docs/review_framework.md](docs/review_framework.md) — dimensions,
  case types, **Cross-Provider Critique Architecture** principles.
- [docs/ai_review_orchestration.md](docs/ai_review_orchestration.md) —
  model roles and stage placement.
- [docs/case_types.md](docs/case_types.md) — thresholds and roles per
  case type.
- [docs/integrity_norms.md](docs/integrity_norms.md) — gating norms.
- [docs/workflows/](docs/workflows/) — YAML recipes the stage runner
  consumes, plus the cold-start runbook.

## Development

```bash
python -m pip install -e ".[dev]"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -p no:cacheprovider
```
