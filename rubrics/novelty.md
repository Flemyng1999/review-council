---
name: novelty
dimension: novelty
description: What is new relative to an explicit literature boundary.
applicable_layers: [macro, chapter]
applicable_case_types: [journal, thesis_master, thesis_phd]
checks:
- id: NOV-01
  text: Literature boundary is explicit ("prior work could do X but not Y; we do Y"), not a vague gap claim.
  severity_if_failed: major
- id: NOV-02
  text: Novelty type is named — phenomenon, mechanism, algorithm, sensor or observation combination, parameterization, reference dataset, or scale.
  severity_if_failed: moderate
- id: NOV-03
  text: Comparison is against the closest current baseline, not against weak or outdated baselines.
  severity_if_failed: major
- id: NOV-04
  text: Architecture or hyperparameter changes are not equated to scientific contribution without an interpretable performance delta.
  severity_if_failed: moderate
- id: NOV-05
  text: thesis_phd hard threshold — an original contribution to knowledge is identifiable. thesis_master — application of established methods to a new context with proper validation suffices.
  severity_if_failed: blocking
---

# Novelty

Sources: NIH Innovation criterion, NeurIPS / ICML / ACL reviewer guidelines,
UK QAA Doctoral Characteristics, Lamont et al. on multi-typed originality.

NIH explicitly notes that work which is not novel may still be critically
important. ACL notes science is incremental and small interesting results
can be significant. For `thesis_undergrad` novelty is not required.
