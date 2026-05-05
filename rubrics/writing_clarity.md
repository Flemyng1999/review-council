---
name: writing_clarity
dimension: clarity
description: Whether an expert reader can re-do the work without contacting the authors.
applicable_layers: [chapter, section, micro]
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: CLR-01
  text: Abstract states problem, data, method, increment, and main result in extractable sentences.
  severity_if_failed: moderate
- id: CLR-02
  text: Each figure answers one specific question; colors are color-blind safe; maps include scale, north arrow, CRS, and acquisition year.
  severity_if_failed: moderate
- id: CLR-03
  text: Units, band ranges, and geometry conventions (solar zenith, view zenith, relative azimuth) are consistent throughout.
  severity_if_failed: moderate
- id: CLR-04
  text: Limitations exist as their own section and are specific, not boilerplate at the end of Discussion.
  severity_if_failed: moderate
- id: CLR-05
  text: An expert reader can re-do the methods without contacting the authors — this is the hard floor.
  severity_if_failed: major
- id: CLR-06
  text: Variable, parameter, and acronym definitions are introduced before first use and remain consistent.
  severity_if_failed: minor
- id: CLR-07
  text: Numbering, cross-references, and citations resolve correctly throughout.
  severity_if_failed: minor
---

# Writing Clarity

Sources: NeurIPS clarity criterion ("a superbly written paper provides
enough information for an expert reader to reproduce its results"),
Greenhalgh "How to Read a Paper", remote sensing journal style guides.

For `thesis_undergrad` the China MOE undergraduate sampling regulation
explicitly evaluates 写作安排 and 逻辑构建 — these map to CLR-01..04.
The "expert reader can re-do" floor is universal.
