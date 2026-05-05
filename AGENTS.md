# AGENTS.md - Agent Rules for review-council

This repository builds a human-AI peer review system. Agents working here should
preserve the distinction between critique, evidence, dissent, and human
judgment.

## Operating Rules

- Read `PROJECT.md`, `WORKING.md`, and `docs/kms_interface.md` before changing
  project structure or review protocols.
- Treat this as a tooling project. Do not impose research-gate progress control
  unless the user explicitly asks for a release gate.
- Put reusable code under `src/review_council/`.
- Keep `scripts/` as thin command wrappers.
- Put concrete manuscript review work under `cases/<case-id>/`.
- Put reusable protocols under `docs/`, copyable artifacts under `templates/`,
  and evaluation criteria under `rubrics/`.
- Do not present AI-generated review text as final editorial judgment.
- Do not make KMS files a runtime dependency of ingestion or validation code.

## Review Case Boundary

Each case should be self-contained enough to reproduce the review trail:
source files, normalized files, review units, evidence, role reviews, decision,
and retrospective.

## KMS Boundary

The repository is the review production system. KMS is the knowledge governance
system. Upgrade reusable lessons to KMS through documented pointers rather than
duplicating governance content inside the repository.

Agents may draft KMS profile or onboarding files inside this repository. Agents
must not directly modify KMS governance files, project profiles, or methodology
cards unless the user explicitly authorizes that action and the KMS rules allow
it.
