---
name: independence
dimension: independence
description: Whether the candidate owns problem framing, methodological choices, execution, and interpretation.
applicable_layers: [macro, chapter]
applicable_case_types: [thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: IND-01
  text: Candidate's individual contribution is explicitly delimited in collaborative work (data acquisition, model code, analysis, writing).
  severity_if_failed: major
- id: IND-02
  text: Methodological choices are defended by the candidate's own reasoning rather than deferred to "supervisor decided".
  severity_if_failed: moderate
- id: IND-03
  text: thesis_phd cumulative — every constituent paper carries a per-paper candidate contribution statement.
  severity_if_failed: blocking
- id: IND-04
  text: Mentor voice (human-only artifact) records candidate's autonomy, decision points, and response to feedback.
  severity_if_failed: major
- id: IND-05
  text: thesis_undergrad — full research training cycle is visible (problem framing, literature, data, analysis, interpretation, writing). Missing stages flagged.
  severity_if_failed: major
- id: IND-06
  text: thesis_phd — candidate can defend the "why" of every methodological choice, not only the "what". Verified in oral defense or chair voice.
  severity_if_failed: major
---

# Independence

Sources: UK QAA Doctoral Characteristics ("substantial independent
contribution"), Salzburg Principles, China MOE 博士学位论文 standards
("独立从事科学研究工作的能力"), Mullins & Kiley examiner research.

Independence is a thesis-only dimension. For collaborative remote-sensing
work, where satellite data, ground observations, and codebases typically
have multiple owners, contribution delimitation is non-optional and not
merely a co-author statement.

The mentor voice artifact is human-only. AI must not generate it.
