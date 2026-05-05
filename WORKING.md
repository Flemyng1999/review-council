# WORKING.md

This file is the current control panel, not a history archive.

## Current Mainline

Bootstrap the review case system: repository skeleton, case layout, ingestion
interfaces, validation, templates, and KMS bridge. This is a tooling project, so
the control panel tracks capability direction rather than strict research
progress.

## Current Objective

Create a minimal runnable structure where a manuscript review case can be
initialized, validated, and filled with source, normalized, unit, evidence,
review, decision, and retrospective files.

## Current Decisions

1. The central object is `cases/<case-id>/`, not a loose prompt or template.
2. `src/review_council/` owns reusable code; `scripts/` should stay thin.
3. `docs/` owns protocols; `templates/` owns copyable case artifacts.
4. KMS integration is low-coupling: repo stores review production records; KMS
   stores reusable principles, rubrics, and upgraded lessons.

## Next Actions

1. Arbiter manually creates `_Governance/project_review-council.yaml` from
   `docs/kms_profile_draft.yaml` if accepted.
2. Use `review-council init-case demo_001` to create the first demo case.
3. Draft the first real ingestion path for either DOCX or TeX.

## Guardrails

- Do not treat AI output as final judgment.
- Do not store long-lived review principles only inside a single case.
- Do not make KMS a runtime dependency of manuscript processing code.
- Do not pretend PDF/DOCX/TeX conversion is solved before test cases exist.
- Do not import gate discipline from research projects unless a specific
  capability needs a release checkpoint.
- Keep concrete case directories ignored by Git unless the user explicitly
  creates a sanitized public fixture.
