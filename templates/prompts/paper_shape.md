---
name: paper_shape
description: Forced gestalt artifact — best version, current shape, top three transformation actions. Anchors all downstream review against the "problem mining" failure mode.
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
inputs: [units/macro/whole.md]
outputs: reviews/paper_shape.md
---

[锚点]
Case `{case_id}`, case_type `{case_type}`. Use only the supplied
manuscript text. Do not invent claims, results, or references.

[假设]
Reviewing is not problem mining. It is judging what the paper should
become. This artifact is the gestalt judgment that anchors all later
critique. Without it, the issue graph and meta-review can list defects
without knowing which defects matter for this paper.

[卡点]
Answer ONLY these three questions, in this order:

1. **What is the best version of this paper?**
   In two to four sentences, describe the strongest possible form this
   work could take. Be concrete (which contribution, which scope, which
   audience), not aspirational.

2. **What is the current actual shape?**
   In two to four sentences, describe what the paper currently is. Note
   tensions between intended and actual.

3. **Top three transformation actions.**
   Three numbered actions, each one sentence + one or two sentences of
   why this action moves the paper toward the best version. Order by
   impact. Avoid generic items (e.g. "improve writing"); name the
   specific chapter, claim, or decision that needs to change.

[边界]
- Output Markdown only. No JSON, no preamble.
- Total length 200 to 400 words. Do not pad.
- For thesis_undergrad: best version means "well-completed undergraduate
  research training", not "publishable in a top journal". Use mentor
  tone.
- Do not produce a list of defects. The defects belong in the issue
  graph; here the question is what shape the paper should take.

[格式]

# Paper Shape

## Best Version

(two to four sentences)

## Current Shape

(two to four sentences)

## Top 3 Transformation Actions

1. **(specific action)** — (1-2 sentence why)
2. **(specific action)** — (1-2 sentence why)
3. **(specific action)** — (1-2 sentence why)
