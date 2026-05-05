# Methodology Alignment

Purpose: record how `review-council` learns from the KMS `_Methodology`
namespace without prematurely creating new KMS cards.

## Honest Current State

The review standards have been deposited in the repository, not yet in KMS:

- `docs/review_standards_research.md`
- `docs/review_framework.md`
- `rubrics/paper_quality_multiscale.md`

This is intentional for now. The user decision is:

- no dedicated review methodology cards yet;
- attach to existing AI-collaboration methodology;
- keep `rubrics/` repo-local;
- do not sync concrete-paper material.

## What Was Learned from `_Methodology`

The KMS `_Methodology` namespace is not just a folder of advice. Its operating
logic is:

1. It is global and project-independent.
2. It stores methods for thinking, writing, research process, and AI
   collaboration, not domain definitions.
3. Each card should carry one principle.
4. Each principle needs source traceability.
5. If a claim is a synthesis across sources, the synthesis responsibility must
   be explicit.
6. Every card needs operational "how to apply" content.
7. Boundaries and exceptions are part of the method, not afterthoughts.
8. Real application records are used before promotion.
9. AI collaboration requires both agency partition and anti-sycophancy.

## Mapping to review-council

| `_Methodology` principle | review-council interpretation |
|---|---|
| One principle per card | One review module per principle |
| Source-backed | Every review standard links to publisher, journal, validation, or thesis rubric sources |
| Synthesis marked | The review framework is marked as repo-side synthesis, not a quoted authority |
| How to apply | The framework is organized as G0-G6 review actions |
| Boundaries | Journal/thesis targets and remote-sensing domain adapters are explicit |
| Application records | Case retrospectives record what the framework caught or missed |
| Axis ⑤ | AI extracts, checks, drafts, and dissents; human owns judgment |
| Axis ⑥ | Dissent review and bias checks are mandatory, not decorative |
| Reproducibility card | Data/code/processing traceability is a core review dimension |
| Incremental validation card | Complex review/rubric modules should be earned by real case evidence |

## Candidate Review Methodology Modules

These are repo-local candidates, not KMS cards:

1. `审稿-目标先定`: judge only after target and threshold are explicit.
2. `审稿-宏观局部双通道`: whole-paper coherence and local evidence both matter.
3. `审稿-主张证据矩阵`: every important claim needs an evidence anchor.
4. `审稿-领域适配`: remote-sensing work must meet physical, validation, and reproducibility norms.
5. `审稿-异议保留`: synthesis must not erase dissent.
6. `审稿-判断归人`: AI can critique but cannot own editorial judgment.
7. `审稿-改进优先`: reviews should maximize useful improvement, not only decide pass/fail.

## Promotion Rule

Do not promote these candidates into KMS immediately.

Promotion should require at least:

- three real or sanitized review cases;
- a retrospective showing the module caught something important;
- at least one boundary/exception discovered in use;
- privacy scrub;
- Arbiter approval.

## Immediate Design Consequence

The repository should treat `docs/review_framework.md` as a working protocol,
not a final doctrine. It should evolve through case retrospectives. KMS receives
only generalized, privacy-safe lessons after evidence accumulates.
