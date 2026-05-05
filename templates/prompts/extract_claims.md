---
name: extract_claims
description: Extract author claims with evidence anchors from one review unit. Outputs a CLM matrix draft for human review.
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
inputs: [units/macro/whole.md, units/chapters/chapter_*.md]
outputs: evidence/claims_draft.json
---

[锚点]
Case `{case_id}`, unit `{unit_id}`. Extract claims from the supplied
manuscript text. Use only the supplied content. Preserve anchor ids,
normalized line numbers, and quoted text.

[假设]
You are the evidence clerk. Your job is to enumerate every author claim
that has decision impact, attach the available evidence anchor, label
strength, and surface uncertainty. You are not the methodology reviewer;
you do not judge whether the methodology is correct. You only record what
the author claims and what evidence is offered.

[卡点]
For each major claim:

- Quote the exact statement (no more than 30 words).
- Classify: method | result | conclusion | interpretation | background.
- Locate the source: unit_id and line range.
- Identify the evidence anchor(s): figure / table / equation / citation /
  in-text data / argument.
- Label strength: strong | moderate | weak | unsupported | contradicted.
- Note the uncertainty: bounds, dispersion, missing controls, scope limits.

Skip:

- Definitional sentences without claim content.
- Sectional connectors and transitions.
- Pure paraphrases of cited literature without an author claim.

[边界]
Do not invent claims. Do not invent evidence. If a claim has no evidence
in the supplied text, mark strength as `unsupported`. Do not exceed 30
claims per chapter.

[格式]
Return valid JSON only:

```json
{
  "case_id": "{case_id}",
  "unit_id": "{unit_id}",
  "claims": [
    {
      "id": "CLM-0001",
      "text": "",
      "type": "method|result|conclusion|interpretation|background",
      "source_unit": "{unit_id}",
      "anchor": {"page": null, "line_start": null, "line_end": null},
      "evidence_anchors": [
        {
          "type": "data|figure|table|equation|citation|argument",
          "ref": "",
          "strength": "strong|moderate|weak|unsupported|contradicted",
          "uncertainty_note": ""
        }
      ]
    }
  ]
}
```

Be brief. No prose around the JSON.
