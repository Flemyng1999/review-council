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

## Cross-Provider Critique Architecture

The strong-model layer of this framework operates under four hard rules.
They are stated together because dropping any one collapses the others
into single-model concatenation — a known failure mode that produced
unusable author reviews before this architecture stabilized (see
`cases/paper_B-jmz/retrospective.md` for the V1–V11 evidence trail).

```text
同模型 multi-run 解决随机性；
跨 provider 独立审稿解决模型家族盲区；
merge 阶段必须保留 single-provider fatal；
最终作者版必须经过 human/editorial rewrite。
```

### Why each rule is non-negotiable

**Same-model multi-run handles sampling variance.** A strong model at
temperature 0.2 still varies run-to-run by ±0.5 hits on an 8-question
methodology rubric — an artefact of the model's sampling, not its
intelligence. Multi-run with light temperature variation
(`--n-runs N --temperature T`) plus per-run dedupe in
`methodology_adversary` smooths this. It does not address what the model
*never* sees.

**Cross-provider critique handles model-family blind spots.** Same-family
models share systematic framing biases: which assumptions they treat as
obvious, which adjacent angles they prefer to explicit ones, which kinds
of statistical critique they avoid. Re-running the same model 10× cannot
escape its family blind spot. Routing the same prompt through a
different provider via the manual adapter
(`--provider manual --external-input ...`) does. On `paper_B-jmz`, V11 =
8/8 vs V10 = 7.25/8 came entirely from this: framings the primary
provider would only reach at adjacent angles were supplied directly by
the second provider.

**The merge stage must preserve single-provider fatal findings.** This
is the most-violated rule in naïve ensembling. The intuition "average
the providers' opinions" produces a majority-vote step, which silently
drops findings only one provider raised. But sharp methodology critique
*is* the case where one reviewer sees what others did not — exactly the
case majority voting suppresses. The framework's
`needs_human_decision` list explicitly escalates every
`single_provider_only AND fatal` finding (and every claim downgrade)
for human review rather than tallying votes against it. **Never replace
this with majority voting.** When in doubt, the merge step under-merges
rather than over-merges; the human cost of collapsing a few duplicated
entries is far below the cost of one provider-only fatal quietly
disappearing.

**Author-facing output must pass through editorial rewrite.** Even with
a perfect adversary stage and a perfect merge, the raw merged JSON is
not deliverable: it leaks model names, internal IDs, severity tokens,
and reads like an internal meta-review. The `author_editorial_rewrite`
stage is the only seam where the final voice (`--voice senior_peer`)
is enforced and `redact_internal_tokens` runs as a final validator
returning a non-zero exit when any leak survives. Skipping this stage
or letting users hand the merged JSON straight to the author defeats
every guarantee above.

### Where these rules are enforced in code

The four rules above are not aspirational; each has a structural
mechanism that prevents future contributors from accidentally
regressing past it:

| Rule | Mechanism | Location |
|---|---|---|
| Same-model multi-run | `--n-runs N` with per-run dedupe via `_dedupe_for_top_level` | `src/review_council/methodology_adversary.py` |
| Provider-agnostic call seam | Single `complete(req, provider=...)` registry; no SDK is imported by stage code | `src/review_council/providers/__init__.py` |
| Single-provider fatal preservation | `needs_human_decision` escalates `(single_provider_only AND fatal)` + every `claim_downgrade` + every severity `conflict` | `src/review_council/adversary_merge.py` |
| Adversary findings survive plan | `_force_merge_adversary` re-attaches dropped fatal items even after a strong model rewrites the plan | `src/review_council/author_editorial.py` |
| Adversary findings survive rewrite | Rewrite prompt's `### 隐藏假设与对照缺口` and `### 论文核心声明的证据匹配度` subsections are mandatory templates with explicit "禁止压平" clauses | `templates/prompts/author_editorial_rewrite.md` |
| No internal tokens reach the author | `redact_internal_tokens` + `find_internal_tokens` validator; CLI exits non-zero on leaks | `src/review_council/author_editorial.py` |
| Stale external-file cache invalidation | Stage fingerprint hashes the contents of `--external-input` and `--input` files | `src/review_council/runner.py` |

### Anti-patterns

These look like improvements and are not. They were considered, tested,
or observed as failure modes during V1–V11; do not reintroduce them.

- **Replacing the cheap fanout with a strong model.** Cheap fanout
  does local issue extraction; strong models do cross-chapter judgment.
  Spending strong-model calls on per-section scans wastes budget without
  raising the upper-bound quality.
- **Majority voting in the merge step.** Drops single-provider fatals.
  See above.
- **Letting the rewrite stage paraphrase fatal items into "please add
  more detail" recommendations.** This was the V7 → V8 failure: the
  model's instinct is to soften assertive critique, and without a
  dedicated subsection template it will. The fix is a template that
  forces the assertive form; do not relax it.
- **Adding new required output types to a strong-model prompt without
  raising the budget floor.** This was the V8 → V9 trade-off: forcing
  `headline_claim_dependencies` into the same `hidden_assumptions ≥ 6`
  budget caused the model to soften other items to make room. New
  required types must come with a higher floor.
- **Designing a richer provider plugin protocol.** The current registry
  is intentionally small (`(CompletionRequest) -> str`). The point is
  one routing seam, not a plugin ecosystem.
- **Hand-fixing the merged JSON instead of feeding it to plan +
  rewrite.** The redaction validator only runs at the final write; any
  channel that bypasses the rewrite stage bypasses the validator.

### Reproducibility status

Validated on N=1 case (`paper_B-jmz`, undergraduate thesis,
quantitative remote sensing). The V11 result (8/8 hard methodology
rubric + 7 bonus findings) is single-run and benefits from this case
being the one the rubric was derived from. The framework's
generalizability across `case_type` (journal, thesis_master, thesis_phd)
and across discipline (non-remote-sensing) is currently unverified.
**Until a second real case validates reproducibility, the framework
should be considered "validated in principle, not in repeated
practice."**

The right next experiment is therefore not further optimization on
`paper_B-jmz` but a clean run on a structurally different case.

### Baseline-And-Integration Extension

After the structured project review has produced a mature author-facing
draft, a high-value validation pattern is:

```text
项目结构化审稿
→ 生成同一原文的多 AI 无结构 baseline 审稿
→ 对多份 comments 做盲审研判
→ 整合最终作者版
```

This extension answers a different question from cross-provider
adversary merge. Cross-provider merge improves the *project pipeline* by
bringing independent methodology findings into `needs_human_decision`.
Unstructured baseline comments test whether the pipeline is outperforming
or merely matching a strong single reviewer. The baseline reviewers must
see only the manuscript, not `issue_graph`, `paper_shape`, adversary
outputs, prior review versions, or project retrospectives.

The integration rule is:

- use the project review for traceable methodology critique and claim
  downgrades;
- use strong baseline comments for natural author voice, implementation
  details, citation/reference checking, and concrete repair language;
- never choose a winner by majority vote;
- treat baseline-only sharp findings the same way as provider-only fatal
  findings: they must be reviewed and either integrated, downgraded, or
  explicitly rejected in the retrospective / decision record.

The expected final author version is therefore not "V11 alone" or "the
best single-AI baseline alone"; it is an editorial synthesis of distinct
reviewer strengths.

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
