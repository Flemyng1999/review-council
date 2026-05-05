# Review Framework

This framework turns the standards research in
`docs/review_standards_research.md` into an executable review structure.

## See Also

- `docs/case_types.md` — five canonical case types and their dimension threshold matrix.
- `docs/integrity_norms.md` — gating norms (COPE, DORA, ICMJE 2026, China MOE).
- `docs/sources.md` — authoritative sources behind every dimension and check.
- `rubrics/*.md` — Skill-style rubrics with YAML frontmatter; the loader selects them by `(case_type, layer)` and injects their checks into prompts.
- `src/review_council/rubrics.py`, `src/review_council/issue_graph.py` — runtime that consumes the rubrics and aggregates per-unit reviews.

## Design Principle

Use one shared core with target-specific adapters.

```text
shared scientific quality core
  + target adapter: journal article / PhD thesis / MSc thesis / BSc thesis
  + field adapter: quantitative vegetation remote sensing / remote sensing /
                   agriculture / environmental physics
  + review depth: triage / full review / revision check / thesis examination
```

This avoids two bad designs:

- one generic checklist that ignores journal-vs-thesis differences;
- separate frameworks that duplicate the same scientific validity checks.

## Methodology Lineage

This framework is repo-local for now, but it follows the `_Methodology`
namespace style:

- one principle per module;
- source-backed claims;
- explicit synthesis responsibility when multiple sources are combined;
- operational "how to apply" steps;
- boundary and exception notes;
- application records from real cases before promotion.

It is attached to the existing AI-collaboration methodology rather than creating
new KMS methodology cards:

- `方法论-科研-AI协作-思考可外包理解不可外包`;
- `方法论-科研-AI协作-反顺从与反偏差`;
- `方法论-科研-可复现性弹药`;
- `方法论-科研-增量验证与简化关联`.

Synthesis responsibility: the review framework is a repo-side synthesis by
review-council, combining publisher reviewer guidance, remote-sensing validation
norms, thesis rubrics, and the existing KMS AI-collaboration methodology. It is
not a direct quotation from any single source.

## Multi-Expert Review Roles

Each role asks a different question. The final review should preserve role
disagreement until the human editor resolves it.

| Role | Main Question | Typical Output |
|---|---|---|
| Human editor/examiner | What judgment is appropriate for this target? | Decision and priorities |
| Domain expert | Does the work make sense in vegetation/RS/ag/env physics? | Physical and field critique |
| Methods/statistics expert | Are design, validation, baselines, and uncertainty sound? | Method defects and fixes |
| Evidence clerk | Which claims are supported, weak, unsupported, or contradicted? | Claim/evidence matrix |
| Reproducibility reviewer | Can another expert reconstruct the work? | Data/code/process audit |
| Dissent reviewer | What is the strongest case against the emerging consensus? | Dissent memo |
| Mentor reviewer | What feedback would most improve the work? | Constructive revision plan |

## Granularity Ladder

Review proceeds from broad to narrow, then back to synthesis.

Principle: global structure comes before local polish, but local evidence can
invalidate global judgment. A review must therefore move down the ladder and
then return upward for synthesis.

### G0 - Target and Threshold

Identify the target before judging quality:

- journal article: target journal, article type, audience, novelty threshold;
- PhD thesis: original contribution and coherent doctoral project;
- MSc thesis: independent research competence;
- BSc thesis: bounded research literacy and correct execution.

Output: `review_target.md`

### G1 - Whole-Paper Judgment

Assess the paper as a system:

- problem importance;
- contribution;
- fit to target;
- scientific story;
- completeness;
- claim/evidence proportionality;
- likely decision.

Output: `reviews/whole_paper.md`

### G2 - Section-Level Review

Assess whether each section does its job:

- title/abstract: accurate promise;
- introduction: gap, motivation, contribution boundary;
- literature: enough and not distorted;
- methods: reproducible and appropriate;
- data: adequate, representative, traceable;
- results: clear and not over-selected;
- discussion: explains significance and limits;
- conclusion: supported, not inflated.

Output: `units/*.md` plus section comments.

### G3 - Claim/Evidence Review

Convert important claims into a matrix:

| Claim | Source unit | Evidence | Strength | Missing check | Decision impact |
|---|---|---|---|---|---|

Strength labels:

- strong;
- moderate;
- weak;
- unsupported;
- contradicted.

Output: `evidence/claim_evidence_matrix.md`

### G4 - Technical Detail Review

Inspect details that can invalidate the work:

- equations and symbols;
- preprocessing steps;
- calibration and correction;
- sampling and validation design;
- uncertainty intervals;
- statistical tests;
- model selection and baselines;
- figures and tables;
- citation appropriateness;
- code/data availability;
- appendix/supplement consistency.

Output: technical issue list with source anchors.

### G5 - Dissent and Bias Check

Before synthesis, force a dissent pass:

- What would make this paper fail despite appearing competent?
- Which major claim is most overconfident?
- What hidden assumption carries the most weight?
- Is the reviewer being too sympathetic, too hostile, or anchored by author
  reputation/topic preference?
- What evidence would change the judgment?

Output: `reviews/dissent.md`

### G6 - Synthesis and Human Judgment

Synthesize without erasing uncertainty:

- strongest merits;
- fatal flaws;
- repairable flaws;
- required revisions;
- optional improvements;
- rejected AI critiques;
- unresolved questions;
- final human-owned judgment.

Output: `decision/editorial_judgment.md`

## Shared Quality Core

Score each dimension qualitatively: excellent / good / adequate / weak /
unacceptable. Do not average scores mechanically; some defects are fatal.

| Dimension | Review Question | Fatal If |
|---|---|---|
| Fit | Does it belong to the target venue/degree? | Target mismatch is fundamental |
| Contribution | What does it add? | No meaningful contribution for target |
| Scientific validity | Do methods/data/analysis support conclusions? | Core inference invalid |
| Evidence strength | Are claims anchored? | Major claims unsupported |
| Field adequacy | Does it meet RS/ag/env physics norms? | Violates domain constraints |
| Validation | Is evaluation independent and representative? | Validation cannot test claim |
| Uncertainty | Are errors and limits quantified or bounded? | Key uncertainty hidden |
| Reproducibility | Can work be reconstructed? | Essential process opaque |
| Communication | Is the argument understandable? | Meaning or method unclear |
| Integrity | Any ethics, citation, plagiarism, or COI issue? | Research record unreliable |

## Target Adapters

### Journal Article Adapter

Add questions:

- Is the contribution publishable for this journal's scope and audience?
- Is novelty/significance enough for this venue?
- Would readers learn something reliable and useful?
- Is the manuscript concise enough for article form?
- What should the editor decide?

Decision categories:

- reject: fatal flaw or insufficient contribution;
- major revision: promising but substantial missing evidence or restructuring;
- minor revision: sound but needs limited clarification/fixes;
- accept: rare without revision.

### PhD Thesis Adapter

Add questions:

- Is there a coherent doctoral research project?
- Is there a substantial original contribution?
- Does the candidate demonstrate command of literature and techniques?
- Are multi-author contributions clearly attributable?
- Do introduction and general discussion integrate the work?
- Can the candidate defend the "why", not just the "what"?

Decision emphasis: degree award readiness, not journal fit.

### MSc Thesis Adapter

Add questions:

- Does the student demonstrate independent research competence?
- Is the question clear and bounded?
- Are methods appropriate and correctly executed?
- Are results interpreted honestly?
- Does the report show adequate literature engagement?

Decision emphasis: competence and disciplined execution, not necessarily high
novelty.

### BSc Thesis Adapter

Add questions:

- Is the scope realistic?
- Is the method basically correct?
- Is execution careful?
- Are limitations honest?
- Is writing and citation practice acceptable?

Decision emphasis: research literacy and bounded technical competence.

## Field Adapter: Vegetation Remote Sensing / Agriculture / Environmental Physics

Add checks:

- sensor/platform/acquisition metadata;
- calibration and atmospheric correction;
- illumination/BRDF/topographic effects;
- spatial, spectral, temporal scale match;
- ground truth/reference-data quality;
- sampling design and independence;
- uncertainty propagation;
- model baselines and ablations;
- cross-site/cross-date/cross-sensor transfer if claims require it;
- physical mechanism consistency;
- agronomic/environmental interpretability;
- operational deployment boundary.

## Review Output Format

Every review should end with:

1. decision or provisional judgment;
2. top 3 strengths;
3. top 3 blocking weaknesses;
4. required revisions;
5. optional improvements;
6. claim/evidence matrix pointer;
7. dissent summary;
8. confidence and limits of the review.

## AI Use Rules

- AI can extract, compare, verify, summarize, and generate dissent.
- AI must preserve source anchors for factual claims.
- AI must name uncertainty and missing expertise.
- AI must not turn review into style preference.
- AI must not own final judgment.
- Human editor/examiner resolves conflicts and decides.

## Application Record

Use this section in case retrospectives:

```text
Case:
Target:
Framework modules used:
What the framework caught:
What it missed:
What should change before the next case:
KMS upgrade candidate:
```
