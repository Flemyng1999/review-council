---
name: reproducibility
dimension: reproducibility
description: Whether the work is reproducible (same data, same result) and replicability is honestly bounded (new data, consistent conclusion).
applicable_layers: [chapter, section]
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: REP-01
  text: Data sources are documented with version, scenes, dates, and acquisition windows (Sentinel-2 L2A version, Landsat Collection 2, MODIS collection, etc.).
  severity_if_failed: major
- id: REP-02
  text: Preprocessing chain is reproducible — masks, thresholds, atmospheric / topographic correction, gap filling, smoothing, and the order of operations.
  severity_if_failed: major
- id: REP-03
  text: Reference data provenance is described — instrument, calibration, sampling design, sample-to-pixel scale matching method (footprint, weighted, ESU).
  severity_if_failed: major
- id: REP-04
  text: CEOS LPV validation stage is stated and not exaggerated. Stage 1 work is not described as "global validation".
  severity_if_failed: major
- id: REP-05
  text: Uncertainty is reported in a GUM / QA4EO style — Type A and Type B components combined; pixel-level uncertainty when applicable; key contributing terms identifiable.
  severity_if_failed: major
- id: REP-06
  text: Reproducibility (same data, same code, same result) is distinguished from replicability (new data, consistent conclusion) when the claim spans both.
  severity_if_failed: moderate
- id: REP-07
  text: Code follows FAIR4RS — DOI-pinned (Zenodo or equivalent), versioned tag, license, dependency lock (environment.yml / requirements.txt / Dockerfile), random seeds fixed.
  severity_if_failed: moderate
- id: REP-08
  text: For pretrained or foundation models, training data does not contain the test region or target year. Data leakage from pretraining is audited.
  severity_if_failed: major
---

# Reproducibility

Sources: NASEM 2019 reproducibility / replicability report, CEOS LPV stages,
JCGM GUM / QA4EO, FAIR and FAIR4RS principles.

NASEM treats failure to replicate as a multi-cause phenomenon (unknown
effect, system variability, hard-to-control variables, substandard practice,
chance). The rubric does not equate "not replicated" with "low quality" — but
it does require that reproducibility (computational) holds and that the
distinction is honored in the manuscript.

For `thesis_undergrad` this rubric is graded with teaching weight. For
`thesis_phd` and `journal` it is graded near hard-threshold.
