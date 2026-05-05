# KMS Interface

Purpose: define the low-coupling bridge between this review repository and the
Obsidian KMS.

## Boundary

The repository owns review production:

- manuscript source files;
- normalized review inputs;
- reviewable units;
- evidence matrices;
- role-specific reviews;
- dissent records;
- editorial decision records;
- case retrospectives;
- ingestion and validation code.

The KMS owns knowledge governance:

- reusable review principles;
- mature rubrics;
- methodology cards;
- recurring failure patterns;
- upgraded lessons from case retrospectives;
- lifecycle status and governance rules.

The two systems should reinforce each other through stable pointers and periodic
synchronization. The repository must not require KMS access to process a case.

This is a tooling project. Unlike a gate-controlled research project, it should
not mirror experimental phase state into KMS. KMS should track stable methods,
rubrics, and lessons; the repository should track concrete capabilities and
case artifacts.

## Write Routing

| Information | First landing point | Upgrade path |
|---|---|---|
| Raw manuscript | `cases/<case-id>/source/` | Never copied to KMS by default |
| Normalized manuscript | `cases/<case-id>/normalized/` | Not synced by default |
| Review unit | `cases/<case-id>/units/` | Not synced by default |
| AI review output | `cases/<case-id>/reviews/` | Not synced by default |
| Human judgment | `cases/<case-id>/decision/` | Not synced by default |
| Case lesson | `cases/<case-id>/retrospective.md` | Only privacy-scrubbed generalized lessons may be manually upgraded |
| Stable protocol | `docs/` | Link from existing AI collaboration methodology for now |
| Rubric | `rubrics/` | Repo-local for now |
| System flaw | `GAPS.md` | KMS only after stable lesson exists |
| KMS registration draft | `docs/kms_profile_draft.yaml` | Arbiter creates official KMS profile |

## Coupling Rules

- Case processing code must run without Obsidian.
- KMS cards should not store volatile per-case review state.
- Repository docs may link to KMS cards but should not duplicate governance
  bodies.
- Retrospectives are the main route from concrete cases to reusable knowledge.
- Raw manuscript files and private review material should not be copied into
  KMS by default.
- The repository `.gitignore` ignores concrete case directories so paper files,
  normalized manuscript text, private reviews, and decisions do not enter Git by
  default.

## Startup Contract for Agents

Before changing project structure, review protocols, or KMS-facing documents,
agents should read:

1. `AGENTS.md`
2. `docs/kms_interface.md`
3. `PROJECT.md`
4. `WORKING.md`

For KMS-facing edits, agents should also inspect the current KMS governance
entry points, but any official KMS-side registration remains Arbiter-owned.
