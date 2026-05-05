---
name: coherence
dimension: coherence
description: Whether the body of work forms a unified research program, not a collection of fragments.
applicable_layers: [macro, chapter]
applicable_case_types: [thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: COH-01
  text: A single research question or thesis claim runs through chapters; each chapter declares its role in the central argument.
  severity_if_failed: major
- id: COH-02
  text: Chapters are connected by explicit transitions, not just by sequential numbering.
  severity_if_failed: moderate
- id: COH-03
  text: thesis_phd cumulative — kappa / synopsis integrates the constituent papers; loose paper collections fail even if each paper was published in a strong venue.
  severity_if_failed: blocking
- id: COH-04
  text: Conclusion integrates findings into a single statement and integrated future work, not chapter-by-chapter recap.
  severity_if_failed: moderate
- id: COH-05
  text: Limitations are integrated across the thesis — interactions between data, method, and validation limits are discussed jointly, not in isolation.
  severity_if_failed: moderate
- id: COH-06
  text: thesis_undergrad — chapter structure is logical (写作安排 / 逻辑构建 per China MOE) and matches the declared research question.
  severity_if_failed: major
---

# Coherence

Sources: PhD by publication policy literature (Mason 2018, Mason & Merga
2018, Tandfonline 2024), Wageningen / Auckland / Cambridge thesis policies,
China MOE 本科毕业论文抽检办法 (写作安排, 逻辑构建).

For thesis_phd cumulative, coherence is the dominant dimension — the kappa
is the thesis, not the sum of papers.

For thesis_undergrad, coherence is grounded in the China MOE sampling axes
of 写作安排 (structural arrangement) and 逻辑构建 (logical construction).
