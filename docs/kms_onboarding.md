# KMS Onboarding Checklist

This file lists the KMS-side work needed to fully register `review-council`.
It is a repository-side checklist. It is not the official KMS record.

## Current State

- Repository-side interface exists: `docs/kms_interface.md`.
- Repo-side final profile draft exists: `docs/kms_profile_draft.yaml`.
- Official KMS governance profile still needs Arbiter-side creation at
  `_Governance/project_review-council.yaml`.
- Project MOC exists: `02-Projects/review-council.md`.
- Dedicated review methodology cards are deferred.
- `rubrics/` remains repo-local for now.
- Anything involving a concrete paper is not synced; `cases/*` is ignored by
  Git except `cases/README.md`.

## What I Can Do in the Repository

- Maintain `docs/kms_interface.md`.
- Draft `docs/kms_profile_draft.yaml`.
- Keep `PROJECT.md`, `WORKING.md`, and `GAPS.md` aligned with the low-coupling KMS boundary.
- Add retrospective templates that identify KMS upgrade candidates.
- Add validation checks that keep case records complete.

## What Needs Arbiter Review

1. Create or approve the official profile:

   ```text
   <VAULT>/_Governance/project_review-council.yaml
   ```

2. Project MOC has been created:

   ```text
   <VAULT>/02-Projects/review-council.md
   ```

3. Attach the project to existing AI collaboration methodology cards rather
   than creating dedicated review methodology cards for now.

4. Preserve the privacy rule:

   - raw manuscripts do not sync to KMS;
   - normalized manuscript text does not sync to KMS;
   - private review text does not sync to KMS;
   - case decisions do not sync to KMS;
   - only privacy-scrubbed, generalized lessons may later become KMS notes.

5. Keep `rubrics/` repo-local for now.

## Suggested Bridge Shape

```text
repo/cases/<case-id>/*
  -> ignored by Git; no KMS sync by default

repo/rubrics/*.md
  -> repo-local for now

repo/docs/*_protocol.md
  -> link from existing AI collaboration methodology, no new card yet

repo/GAPS.md
  -> KMS only when a gap becomes a generalized lesson
```

## Non-Goals

- Do not copy manuscript files into KMS.
- Do not store volatile per-case review state in KMS.
- Do not make case processing code depend on vault access.
- Do not force research-project gate discipline onto this tooling project.
