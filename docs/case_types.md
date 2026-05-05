# Case Types

A case type determines which dimensions are scored, which thresholds apply,
and which reviewer roles are required. The framework recognizes five canonical
types.

## Taxonomy

```text
case_type:        journal | thesis_undergrad | thesis_master | thesis_phd
thesis_format:    monograph | cumulative          # required when case_type = thesis_phd
discipline:       remote_sensing | agronomy | env_physics | ...
```

The manifest carries these fields. Validation should check that
`thesis_format` is present and one of the two values when
`case_type = thesis_phd`.

## Type Definitions

### journal
A submission to a peer-reviewed journal. Evaluated as a research product
without reference to author training. Default-reject posture — burden is on
the manuscript to justify publication.

### thesis_undergrad
Undergraduate thesis or capstone project. Primary purpose is to certify that
the student has completed a full research training cycle (problem framing →
literature → data → analysis → interpretation → writing) at the undergraduate
level of expected competence. **Originality is not required.** Major risk:
ghost-writing, plagiarism, fabrication, training cycle gaps.

Capstone variants (less data depth, shorter format) use the same framework
with relaxed methodology and evidence thresholds.

### thesis_master
Master's thesis. Demonstrates competent application of established methods to
a new context (new region, crop, sensor combination, year). Originality
threshold low — applying existing methods to a new setting with proper
validation suffices. Major risk: methodology gaps, incomplete uncertainty
treatment.

### thesis_phd (monograph)
Doctoral monograph. Hard threshold: original contribution to knowledge.
Single research argument runs through all chapters. Examiner default-pass
posture (Mullins & Kiley) — dissent must be intensified. Foundational
Mastery hard threshold — introduction must demonstrate solid breadth and
systematic depth in the domain.

### thesis_phd (cumulative)
Doctoral thesis by publication. The thesis is the **integration narrative**
(kappa / synopsis), not the sum of papers. Hard threshold: thematic
coherence and explicit per-paper candidate contribution. Each constituent
paper must be related to the central question; loose paper collections fail
even if every paper was published in a strong venue.

## Dimension Threshold Matrix

H = hard threshold (failing this fails the case).
✓ = scored normally. — = not applicable.
Low/Mid/High = expected level for this type.

| Dimension | journal | undergrad | master | phd_monograph | phd_cumulative |
|---|---|---|---|---|---|
| Significance | High | Low | Mid | High | High |
| Novelty | High | — | Low–Mid | **H** | **H** |
| Methodology | High | Mid | High | High | High |
| Evidence Strength | High | Mid | Mid–High | High | High |
| Reproducibility | Mid–High | Low–Mid | High | High | High |
| Writing Clarity | High | **H** | High | High | **H** |
| Independence | — | Low | Mid | **H** | **H** |
| Coherence | — | Mid | Mid–High | High | **H** |
| Foundational Mastery | — | Mid (UG level) | Mid–High | **H** | Mid–High |

## Reviewer Role Matrix

✓ = required. ✓✓ = intensified for this type. — = not used.

| Role | journal | undergrad | master | phd_* |
|---|---|---|---|---|
| Primary reviewer | ✓ | ✓ | ✓ | ✓ |
| Verifier | ✓ | ✓ | ✓ | ✓ |
| Dissent reviewer | ✓ | ✓✓ | ✓✓ | ✓✓ |
| Synthesis writer | ✓ | — | ✓ | ✓ |
| Mentor / chair voice (human-only) | — | ✓ | ✓ | ✓ |
| Integrity / process check | weak | ✓✓ | ✓ | ✓ |
| Disciplinary breadth reviewer | — | — | optional | ✓ |
| Editorial decision (human-only) | ✓ | ✓ | ✓ | ✓ |

The mentor voice and final editorial decision are human-only artifacts. AI
must not generate them.

## Field-Specific Pass Profiles

Typical accepted forms in vegetation quantitative remote sensing,
agriculture, and environmental physics:

| Type | Typical pass profile |
|---|---|
| journal | New algorithm, parameterization, dataset, or phenomenon evidence; CEOS LPV Stage 2+ validation; GUM-style uncertainty. |
| thesis_undergrad | Existing inversion or model (PROSPECT-SAIL, NDVI-LAI, etc.) applied to one dataset; structured comparison; clean writing; full citation hygiene. |
| thesis_master | Existing method applied to a new region, crop, sensor, or year; scale-matching and uncertainty discussed; cross-condition validation attempted. |
| thesis_phd_monograph | New retrieval framework, new parameterization, or new cross-scale method; systematic validation; explicit error propagation; foundations chapter. |
| thesis_phd_cumulative | 3–5 thematically linked papers + integration kappa; per-paper contribution statement; integrated limits and future work. |

## Manifest Fields

Until the manifest schema is updated in code, the YAML can carry:

```yaml
case_id: example_001
case_type: thesis_phd
thesis_format: monograph
discipline: remote_sensing
title: 'Example title'
status: initialized
```

`case/manifest.py` and `case/validate.py` should be updated to require
`case_type:` as a manifest key, and to validate `thesis_format` when
`case_type` is `thesis_phd`.
