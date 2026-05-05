---
name: evidence_strength
dimension: evidence
description: Whether each important claim is supported with strength matching its boldness.
applicable_layers: [chapter, section]
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: EVD-01
  text: Each major claim has a direct evidence anchor (figure, table, equation, dataset, or cited source); conclusions are not asserted.
  severity_if_failed: major
- id: EVD-02
  text: Effect size and confidence intervals are reported alongside p-values; significance is not used as evidence ceiling.
  severity_if_failed: major
- id: EVD-03
  text: Causal or attribution claims pass a Bradford Hill self-check — strength, consistency, temporality, dose-response, plausibility, coherence — or are softened to associations.
  severity_if_failed: major
- id: EVD-04
  text: Conclusions are narrower than or equal to the evidence; no extrapolation to unsampled regions, seasons, sensors, or conditions.
  severity_if_failed: major
- id: EVD-05
  text: Failure cases, boundary conditions, or counter-examples are shown rather than hidden.
  severity_if_failed: moderate
- id: EVD-06
  text: NDVI / EVI or other vegetation indices used as proxies for GPP, LAI, or yield are reported with their saturation and non-linearity caveats, not as direct measures.
  severity_if_failed: moderate
---

# Evidence Strength

Sources: Bradford Hill viewpoints, NIH Rigor criterion, COPE evidence
expectations, Sense About Science peer review guidance.

A claim can be well written and still weakly evidenced. The evidence rule is
strength-matching: the boldness of the claim must not exceed the strength of
its anchor. Significance figures with no effect size, and correlations
labeled as drivers, are the two highest-frequency evidence violations in
this domain.
