---
name: paper_quality_multiscale
dimension: ""
description: Reading guide that maps macro / meso / micro / RS layers to dimensions. Not a checked rubric; the loader skips it for prompt injection.
applicable_layers: []
applicable_case_types: []
checks: []
---

# Multiscale Paper Quality Rubric

Cross-reference for `docs/review_framework.md`. The dimension-keyed rubrics
(`significance.md`, `novelty.md`, `methodology.md`, `evidence_strength.md`,
`reproducibility.md`, `writing_clarity.md`, `independence.md`, `coherence.md`,
`foundational_mastery.md`, `scope_and_ethics.md`) carry the actual checks
loaded into prompts. This file is kept as a quick reading map.

## Macro Layer

| Dimension | Excellent | Weak |
|---|---|---|
| Problem | Important, precise, field-relevant | Vague or trivial |
| Contribution | Clearly new/useful for target | Incremental without justification |
| System completeness | Research story is coherent end to end | Missing major component |
| Scientific claim | Claims are proportional to evidence | Claims exceed evidence |
| Target fit | Matches venue/degree expectations | Mis-targeted |

## Meso Layer

| Section | Must Do |
|---|---|
| Abstract | State problem, method, main result, implication accurately |
| Introduction | Establish gap, stakes, contribution boundary |
| Literature | Position against relevant current work |
| Methods | Enable expert reconstruction |
| Data | Identify source, quality, representativeness, limits |
| Results | Present evidence without over-selection |
| Discussion | Interpret, compare, limit, and explain implications |
| Conclusion | State only supported conclusions |

## Micro Layer

| Element | Check |
|---|---|
| Claim | Has direct evidence anchor |
| Equation | Symbols defined and derivation valid |
| Figure | Interpretable without misleading design |
| Table | Supports a specific claim |
| Citation | Correct source and not ornamental |
| Validation | Independent and appropriate |
| Uncertainty | Quantified or bounded |
| Code/data | Available or restriction justified |

## Remote-Sensing Layer

| Dimension | Check |
|---|---|
| Sensor | Platform, bands, resolution, calibration reported |
| Geometry | Viewing/illumination/topography handled or bounded |
| Preprocessing | Atmospheric correction, masks, filtering traceable |
| Reference data | Spatial/temporal quality and sampling design adequate |
| Scale | Pixel/plot/canopy/field scale mismatch handled |
| Baseline | Comparisons are fair and relevant |
| Transferability | Generality tested where claimed |
| Physics | Mechanism does not violate known constraints |

## Target Adapter

Use the same rubric differently by target:

- Journal: contribution + soundness + fit drive decision.
- PhD thesis: original coherent contribution + candidate ownership drive
  decision.
- MSc thesis: independent competence + correct execution drive decision.
- BSc thesis: bounded research literacy + honest reporting drive decision.
