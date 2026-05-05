---
name: foundational_mastery
dimension: foundational_mastery
description: Whether the candidate demonstrates breadth and depth appropriate to the degree level.
applicable_layers: [macro, chapter]
applicable_case_types: [thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: FND-01
  text: Introduction or literature chapter demonstrates relevant breadth of the field — not a narrow citation set centered on a single research group.
  severity_if_failed: major
- id: FND-02
  text: Methods chapter demonstrates command of underlying theory — radiative transfer fundamentals, error propagation, statistical inference, sensor physics — at the expected degree level.
  severity_if_failed: major
- id: FND-03
  text: Discussion shows command of competing interpretations and alternative methods, not only the one used.
  severity_if_failed: moderate
- id: FND-04
  text: thesis_phd hard threshold — solid breadth (坚实宽广的基础理论) AND systematic depth (系统深入的专门知识) per China MOE.
  severity_if_failed: blocking
- id: FND-05
  text: thesis_master — competent application of established methods to a new context with proper validation; foundational understanding visible in defense of choices.
  severity_if_failed: major
- id: FND-06
  text: thesis_undergrad — undergraduate-level mastery of the specific tools used; over-claiming systematic depth is not required and not credit-worthy.
  severity_if_failed: moderate
---

# Foundational Mastery

Sources: UK QAA Doctoral Characteristics, China MOE 博士学位论文标准
("坚实宽广的基础理论, 系统深入的专门知识"), Salzburg Principles,
Wageningen MSc / PhD rubrics.

This dimension is graded at the level appropriate to the degree.
Undergraduate thesis is not measured against PhD foundational depth.
PhD work that fails breadth or depth fails the dimension hard.
