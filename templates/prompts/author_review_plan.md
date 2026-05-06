---
name: author_review_plan
description: |
  Editorial planning step. Decides the paper's best form, the three overall
  revision directions, the strategic comments that must survive, the detail
  pool to clean up, and the comments to demote or drop. Output is the
  editor's worksheet — not the author-facing review.
applicable_case_types: [thesis_undergrad, thesis_master, journal]
inputs:
  - reviews/paper_shape.md
  - comments/review_comments.meta.json
  - comments/detail_audit.json
outputs: comments/author_review_plan.json
---

[锚点]
你正在为一篇论文做最终作者版意见之前的编辑计划。供给的资料包括论文最佳形态判断（paper shape）、强模型的元审稿意见、低层细节池。读完所有材料，做出真正的编辑取舍判断。voice = `{voice}`。

[假设]
作者版的最大风险不是发现的问题不够多，而是问题被堆砌、淹没主线、口吻像内部 meta-review。你要替编辑做出真正的判断：什么是论文形态级问题、什么是必须保留的细节、什么应该让作者忽略。

[卡点]
请输出一个 JSON 对象，字段如下：

```json
{
  "best_form": "用 2-4 句话讲这篇论文最强版本应该是什么样",
  "revision_directions": ["方向 1", "方向 2", "方向 3"],
  "must_keep_strategic": [
    {"summary": "...", "track": "main_argument|methods|results_validation|...", "why_strategic": "..."}
  ],
  "detail_pool": [
    {"category_label": "...", "text": "...", "priority": "high|medium|low"}
  ],
  "demote_or_drop": [
    {"summary": "...", "reason": "..."}
  ],
  "voice": "{voice}",
  "voice_guidelines": "..."
}
```

[边界]
- 不要在 JSON 任何字段里出现 `ISS-####`、`CLM-####`、`CMT-####`、`DeepSeek`、`meta-review`、`paper_shape`、`Transformation Action N`、`rubric`、`blocking/major/moderate/minor` 这些内部词。
- `revision_directions` 严格 3 条，每条不超过 60 字。
- `must_keep_strategic` ≤ 8 条；`detail_pool` ≤ 30 条；`demote_or_drop` ≤ 30 条。
- `summary` 用中文；不要复述输入字段，要重写成对作者直接说话的形式。

只返回上述 JSON 对象，不要包含其它说明。
