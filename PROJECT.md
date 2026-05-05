# PROJECT.md - Stable Project Spine

This repository builds a human-AI peer review system for structured critique,
evidence tracking, dissent, and accountable editorial judgment.

## Core Position

AI may produce critique, extract evidence, identify omissions, and stress-test
arguments. Final judgment belongs to a human editor or reviewer.

The project is not a prompt collection. It is a review production system:
raw manuscripts are ingested, normalized, segmented into reviewable units,
linked to claim-level evidence, reviewed by multiple roles, and resolved by
human editorial judgment.

## Object Model

The central unit is a review case:

```text
cases/<case-id>/
```

A case owns the source manuscript, normalized text, review units, evidence
records, reviewer outputs, decision records, and retrospective notes.

## Layers

1. Object layer: raw paper files, attachments, normalized manuscript, figures,
   tables, references, and reviewable units.
2. Review layer: claim/evidence matrices, role-specific reviews, dissent, and
   synthesis.
3. Judgment layer: editorial decisions, required revisions, open questions, and
   human accountability.
4. Governance layer: protocols, rubrics, templates, gaps, retrospectives, and
   KMS upgrade routes.

## Initial Scope

The first usable version supports one manuscript review case end to end:

- ingest a `.docx`, `.tex`, or `.pdf` source into a case directory;
- maintain a manifest that records source files and processing status;
- normalize manuscript content into Markdown;
- split content into reviewable units;
- record evidence, reviews, dissent, and final human judgment.

Conversion quality will improve incrementally. The first invariant is traceable
case structure, not perfect parsing.

## Project Type

This is a tooling project, not a gate-controlled research project. It does not
need strict phase progress, experimental gates, or daily verdict pressure.

Progress should be organized around usable capabilities:

- case initialization and validation;
- manuscript ingestion for DOCX, TeX, and PDF sources;
- normalization into review-ready Markdown and extracted assets;
- segmentation into reviewable units;
- evidence matrix construction;
- role-specific review generation;
- dissent preservation;
- human-owned decision records;
- retrospective-to-KMS upgrade routes.

## KMS Relationship

The repository is the production system for concrete review cases. KMS is the
governance system for reusable knowledge.

Repository-owned:

- case files and manuscript artifacts;
- source-to-normalized conversion outputs;
- evidence matrices;
- role reviews and dissent records;
- human decision records;
- tooling code and tests;
- per-case retrospectives.

KMS-owned:

- reusable review principles;
- mature rubrics;
- repeated failure patterns;
- methodology cards;
- project-level MOC and lifecycle metadata.

The bridge is low-coupling: case tooling must run without KMS access. KMS should
receive only reusable lessons and stable protocol/rubric upgrades, not raw
manuscripts or volatile case state.
