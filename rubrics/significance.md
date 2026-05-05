---
name: significance
dimension: significance
description: Whether the work, if correct, would change thinking or practice for the target audience.
applicable_layers: [macro, chapter]
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: SIG-01
  text: The work leads with an environmental, agronomic, or physical question; algorithm or technique is in service of that question.
  severity_if_failed: major
- id: SIG-02
  text: If the conclusion held, a specific audience would change a decision, model assumption, or downstream product.
  severity_if_failed: major
- id: SIG-03
  text: Spatial extent, temporal extent, biome, and sensor conditions over which the claim applies are explicit.
  severity_if_failed: major
- id: SIG-04
  text: Incremental contributions are framed honestly; replication, scope extension, and uncertainty reduction are accepted as legitimate forms of significance.
  severity_if_failed: minor
- id: SIG-05
  text: Significance is justified on content, not on venue prestige or institutional affiliation (DORA).
  severity_if_failed: moderate
---

# Significance

Sources: Nature editorial criteria, NIH Factor 1 (Importance of the Research),
Remote Sensing of Environment guide for authors, DORA. RSE explicitly notes
that algorithm-only framing without an environmental question is a frequent
desk-reject reason.

For `thesis_undergrad` the bar is "relevant to the discipline at undergraduate
level". For `thesis_phd` alignment with frontier or applied need is expected.
For `journal` the test is whether the result matters broadly enough to change
thinking in the field.
