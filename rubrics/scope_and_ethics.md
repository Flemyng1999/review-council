---
name: scope_and_ethics
dimension: integrity
description: Cross-cutting integrity, ethics, and scope norms. Failing any check invalidates dimension scoring rather than reducing it.
applicable_layers: [macro, chapter, section]
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: INT-01
  text: AI tool use is disclosed — writing assistance in acknowledgments, data analysis or figure generation in methods (ICMJE 2026 logic).
  severity_if_failed: major
- id: INT-02
  text: Conflicts of interest (financial, personal, academic competition) are declared.
  severity_if_failed: major
- id: INT-03
  text: Data licensing, consent, privacy, and re-use permissions are honored when applicable (UAV imagery over private land, satellite product licenses, in-situ data agreements).
  severity_if_failed: major
- id: INT-04
  text: Citation hygiene — quotations, paraphrases, and figure reuses are traceable to sources; no orphan citations or borrowed framings without attribution.
  severity_if_failed: major
- id: INT-05
  text: Plagiarism similarity report and AI-detection report (when applicable, especially thesis_undergrad) have been reviewed; matches above thresholds are investigated.
  severity_if_failed: blocking
- id: INT-06
  text: For collaborative work, candidate's individual contribution is delimited (especially thesis_phd cumulative — per-paper statement).
  severity_if_failed: major
- id: INT-07
  text: Fabrication red flags absent — writing-style discontinuities, professional capability matched to artifact complexity, raw data exists, code version history exists.
  severity_if_failed: blocking
- id: INT-08
  text: Conclusions stay within evidence; limitations are specific; no overgeneralization from a single site, year, or sensor configuration.
  severity_if_failed: moderate
- id: INT-09
  text: Significance is judged by content — DORA — not by venue prestige.
  severity_if_failed: minor
---

# Scope and Ethics

Sources: COPE peer review ethics, ICMJE 2026 AI disclosure, DORA,
China MOE undergraduate sampling regulation (学术规范), QA4EO data
provenance.

This rubric is a gate, not a dimension score. Failures here invalidate
dimension scoring rather than reducing it. INT-05 and INT-07 are blocking
for thesis cases; merely "lower the score" is not an acceptable response.

This rubric is consumed by the `integrity_check` artifact, not by general
dimension review.
