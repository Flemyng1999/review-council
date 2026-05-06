# Cold-Start Runbook: Reviewing a Case End-to-End

> 给一个**第一次接触这个仓库的 AI session 或新贡献者**用的执行手册。读完这一篇 + 它链接的 5 个文档，你就可以把一个新 case 从原文跑到可交付的作者版意见，并且不会退回到旧的单模型拼接流程。
>
> 本文不重复原则，只把原则**变成可执行步骤**。原则的 single source of truth 是 [`docs/review_framework.md`](../review_framework.md) 的 "Cross-Provider Critique Architecture" 章节。

---

## 0. 必读（按顺序读完再开始动手）

任何审稿/case execution/prompt 修改/workflow 调整动作之前，必须先读：

1. [`PROJECT.md`](../../PROJECT.md) — 项目定位：tooling project，不是研究 gate 项目。
2. [`WORKING.md`](../../WORKING.md) — 当前 control panel；不读容易把"已完成"当成"待做"。
3. [`docs/review_framework.md`](../review_framework.md) — 框架原则。**Cross-Provider Critique Architecture 那一节是硬约束**。
4. [`docs/ai_review_orchestration.md`](../ai_review_orchestration.md) — 模型角色 + 强模型放在哪几个 stage。
5. 对应 case_type 的 workflow yaml，例如 [`docs/workflows/thesis_undergrad.yaml`](thesis_undergrad.yaml) — 真实 stage 顺序、真实命令、真实 flag。

辅助：[`docs/paper_ingestion_protocol.md`](../paper_ingestion_protocol.md) (DOCX/PDF → frozen → MinerU)、[`docs/MinerU使用指南.md`](../MinerU使用指南.md)。

**不要跳过这五份就开始改 prompt 或 workflow。** 跑偏的代价远高于读文档的时间。

---

## 1. 角色边界（先认清）

| 你是谁 | 你能做什么 | 你不能做什么 |
|---|---|---|
| AI session（包括我） | 生成 critique、抽取 evidence、填 detail audit、产出 plan 的草稿、产出 author 版的草稿 | 拍最终编辑判断、决定接收/拒稿、把 AI 输出当作 final review 发给作者 |
| 人工 reviewer / 编辑 | 审阅 AI 草稿、resolve `needs_human_decision`、写 `decision/editorial_judgment.md`、写 `dissent.md`、写 `integrity_check.md` | 越过 redaction validator 把含内部 token 的草稿发出去 |

**最终作者版只能由 `author_editorial_rewrite` stage 产出，并且必须经过 `redact_internal_tokens` validator。** 不要把 `reviews/issue_graph.json`、`reviews/methodology_adversary.merged.json`、`comments/author_review_plan.md` 中任何一个直接发给作者——它们带内部 ID、严重度标签、provider 名称，泄露内部生产链。

---

## 2. Case 隐私边界

- `cases/` 是隐私数据。**不要 `git add cases/`，不要 `git commit cases/`，不要把 case 内容复制进 docs/AGENTS/README/测试 fixture。**
- 可以引用 case id（例如"`paper_B-jmz` 在 retrospective 中是 N=1 验证案例"），但不要复制其中的论文事实、审稿意见或具体数值进文档。
- 测试用最小假数据，不要从 case 文件粘内容。

---

## 3. 完整 V11 流程（thesis_undergrad，端到端）

### 阶段 A：初始化 + 摄入

```bash
# 1) 创建 case 骨架
python -m review_council.cli init-case <case-id> --case-type thesis_undergrad --discipline <discipline>

# 2) 把原文放进 cases/<case-id>/source/
#    DOCX → 用 Microsoft Word 导出 PDF，存为 cases/<case-id>/frozen/manuscript.pdf
#    PDF  → 直接拷贝/symlink 到 cases/<case-id>/frozen/manuscript.pdf

# 3) 在 GPU 主机上跑 MinerU（生成 normalized/manuscript.md + provenance/source_map.jsonl）
ssh ubuntu-303 -p 5422
bash scripts/mineru_case_extract.sh cases/<case-id>/frozen/manuscript.pdf cases/<case-id>

# 4) 验证 case 结构
python -m review_council.cli validate-case cases/<case-id>
```

### 阶段 B：跑 workflow 第一遍（自动 stage + 廉价 fanout + 强模型主链）

```bash
# 列出会跑的 stage（不要漏看哪些是 human gate）
python -m review_council.cli review-case cases/<case-id> --list

# 实际跑：自动 stage 全部跑完，碰到 human gate 会停下并打印指令
python -m review_council.cli review-case cases/<case-id>
```

第一遍跑完后，`reviews/methodology_adversary.json`（deepseek 主线）、`reviews/methodology_adversary.secondary.json`（manual provider 写出的 `manual_pending` stub）、`reviews/methodology_adversary.merged.json`（merge 阶段把单 deepseek 当作单源处理）、`comments/author_facing_comments.md`（author_editorial_rewrite 的初版）都已经存在。

**这一步不是终点。** Cross-provider 是这个框架的核心增量；只有 deepseek 一边的输出叫"V10 等价"，不叫 V11。

### 阶段 C：cross-provider secondary（manual provider 主流程）

`methodology_adversary_secondary` stage 第一遍跑出 stub，同时把渲染好的 prompt 写到：

```
cases/<case-id>/reviews/methodology_adversary.secondary_prompt.md
```

接下来：

1. **把 prompt 文件的全文** 复制到一个外部 LLM（Claude、ChatGPT、Gemini、本地大模型，任意 provider）。
2. 让那个外部模型按 prompt 的 schema 输出 JSON（hidden_assumptions / unmet_research_goals / headline_claim_dependencies）。
3. **把外部模型的完整响应**保存到：

```
cases/<case-id>/reviews/methodology_adversary.secondary_response.txt
```

4. 重新跑 workflow：

```bash
python -m review_council.cli review-case cases/<case-id>
```

   - `methodology_adversary_secondary` 这次会读到响应文件，写出真实的 secondary adversary JSON。
   - `merge_methodology_adversaries` 会被 stage fingerprint 检测到 `--external-input` 内容变化而重跑（这一行为由 `runner.py` 的外部文件 hash 保证）。
   - `author_review_plan` 重跑，把 merged adversary 中所有 fatal/major + 所有 claim_downgrade + 所有 unmet_goal 强制并入 `must_keep_strategic`，把 `needs_human_decision` 透传到 plan。
   - `author_editorial_rewrite` 重写 `comments/author_facing_comments.md`，并跑 redaction validator。

如果你想跑同模型多次降低采样方差，单独调一次 primary：

```bash
python -m review_council.cli methodology-adversary \
  cases/<case-id>/units/chapters/chapter_01.md \
  cases/<case-id>/units/chapters/chapter_03.md \
  cases/<case-id>/units/chapters/chapter_04.md \
  cases/<case-id>/reviews/methodology_adversary.json \
  --case-id <case-id> --provider deepseek --n-runs 3 --temperature 0.2
```

然后重跑 `review-case`。

### 阶段 D：必须人工检查的输出

按这个顺序看：

1. `cases/<case-id>/reviews/methodology_adversary.merged.md` — 看 `agreement` 分类；特别看 **needs_human_decision** 列表，每一项要么人工裁决要么写进 `decision/editorial_judgment.md`。
2. `cases/<case-id>/comments/author_review_plan.md` — 看编辑计划：3 条 revision_directions、must_keep_strategic、demote_or_drop 是否合理。
3. `cases/<case-id>/comments/author_facing_comments.md` — **这是要发给作者的文件**。检查：
   - 第一段不是机械模板；
   - "总体修改方向"列了 3 条；
   - "§二、方法与可复现性"下有 "### 隐藏假设与对照缺口" 子节，且每条隐藏假设保留了 fatal/major 级别的语气（**不是**被译成"please add more detail"）；
   - "§三、结果解释与证据强度"下有 "### 论文核心声明的证据匹配度" 子节（如果 adversary 产出了 claim_downgrade）；
   - 末尾有 "## 建议的修改顺序"；
   - **没有任何**字眼：DeepSeek、Claude、ChatGPT、GPT、Anthropic、OpenAI、ISS-####、CMT-####、MA-####、MERGE-####、paper_shape、Transformation Action、issue graph、rubric、blocking/major/moderate/minor。

### 阶段 E：剩余的人工 gate（按 yaml 顺序）

- `claim_matrix_review` — 编辑 `evidence/claim_evidence_matrix.json`，给 claim 打 ID、修锚点、标证据强度。
- `dissent` — 写 `reviews/dissent.md`（thesis_undergrad 用 `templates/prompts/dissent_thesis.md`）。
- `integrity_check` — 写 `reviews/integrity_check.md`。
- `editorial_decision` — 写 `decision/editorial_judgment.md`。
- `retrospective` — 更新 `cases/<case-id>/retrospective.md`：什么被框架抓到、什么没抓到、是否有应升 KMS 的可复用教训。

### 阶段 F：可选的单 AI baseline + comments 整合

当需要评估框架是否真的优于"强单 AI 一次性审稿"，或需要进一步提高最终作者版的自然度时，可在项目审稿完成后加一轮 baseline：

1. 只把原文 Markdown/PDF 给 2–3 个外部 AI。不要给它们 `paper_shape`、`issue_graph`、`methodology_adversary`、`author_review_plan`、历史版本 comments 或 retrospective。
2. 要求它们按"单 AI + 无结构审稿"输出作者版 comments。
3. 把这些文件放入 case 的 `comments/` 目录，例如 `comments.A.md`、`comments.B.md`、`comments.C.md`。
4. 盲审比较：主线判断、硬方法命中、隐藏假设识别、作者可执行性、作者版语气。
5. 最终整合时不要做多数票。项目结构化审稿负责方法论深度和证据链，baseline comments 负责自然语气、实现细节、文献核对和作者可执行措辞。baseline-only 的尖锐发现必须被整合、降级或在 retrospective 中明确拒绝。

这一步不是每个 case 的必跑 stage；它是评估和打磨 final author comments 的人工/编辑增强流程。原则见 `docs/review_framework.md` 的 "Baseline-And-Integration Extension"。

---

## 4. 反模式（**不要做**）

这些都已经在 V1–V11 实跑里翻车过，原则在 `docs/review_framework.md` 的 "Anti-patterns" 段，这里只列冷启动场景下最常见的错误：

- ❌ **跳过 manual secondary**，只跑 deepseek 一遍就把 author 版发出去。这只到 V10 水平，丢掉的就是 single-provider blind spot 的对冲。
- ❌ **绕过 `author_editorial_rewrite`**，把 `comments/review_comments.meta.json` 或 `reviews/methodology_adversary.merged.json` 自己粘成作者版。redaction validator 不会跑，内部 token 会泄露。
- ❌ **看到 `compose_author_review` 和 `author_polish` 还在 yaml 里，就以为它们是主链。** 它们是 V6 era 的 fallback——`author_editorial_rewrite` stage 在它们之后跑，会覆盖同一个 `comments/author_facing_comments.md`。canonical = `author_editorial_rewrite` 的输出。
- ❌ **把 strong model 用到 deepseek_chapters / deepseek_sections fanout**。强模型放在 `paper_shape`、`meta_review_issues`、`methodology_adversary`、`author_review_plan`、`author_editorial_rewrite` 这 5 个高杠杆 stage 即可，廉价 fanout 不要替换，否则烧钱不提质。
- ❌ **对 merge 阶段做 majority voting**。`needs_human_decision` 必须保留 single-provider fatal、所有 claim_downgrade、所有 severity conflict。多数票会把"一个人看到了别人没看到"这种最有价值的 critique 静默丢掉。
- ❌ **在 prompt 里加新的必填输出类型，但不抬 `hidden_assumptions ≥ 8` 的下限**。模型会在既有项目里软化以腾预算，导致旧覆盖度回归。详见 `docs/review_framework.md` Anti-patterns。
- ❌ **redaction validator 非零退出的草稿，仍然发给作者**。CLI 会打印 `WARNING: N internal tokens leaked: ...` 并 exit 1；这时必须修，不是忽略。
- ❌ **把 case 内容写进 docs / README / AGENTS / 测试 fixture**。`cases/` 是隐私边界。
- ❌ **把这个项目当成有研究 gate 进度控制的科研项目**。它是 tooling 项目，没有"phase 完成 / 进入下一 phase"语义。

---

## 5. 什么时候停止优化同一个 case

冷启动 AI 容易陷入"再多调一轮就能更高分"。在这个项目，这是边际负收益区。**判停信号：**

- 当前 case 上单轮硬命中已经在 7/8–8/8（rubric 题数视 case 而定）；
- 上一轮 prompt 调整带来的提升 < 0.5；
- `needs_human_decision` 的人工裁决比 prompt 微调更影响最终质量；
- 还没有第二个真实 case 被同一框架跑过。

满足后三条任意两条 → 不要跑 V12，去找/等第二个 case，或者把当前 case 的 retrospective 写完。

V11 在 N=1 case (`paper_B-jmz`) 上达到 8/8。**这不等于框架在跨 case 上已验证**。`docs/review_framework.md` 里把它归类为 "validated in principle, not in repeated practice"。冷启动 AI 看到 V11 评分不要据此放弃在新 case 上的方法论怀疑——**新 case 第一遍跑完后，主动检查 needs_human_decision，不要假设 deepseek+manual 的两轮已经覆盖所有盲区**。

---

## 6. 故障排查（按出现频率）

| 症状 | 原因 | 处理 |
|---|---|---|
| `methodology_adversary_secondary` 一直是 `manual_pending` | 没有把外部 LLM 响应写到 `secondary_response.txt` | 写进去再跑 `review-case` |
| 改了 `secondary_response.txt`，重跑时 secondary stage 被 cache 跳过 | 旧版 stage fingerprint 不 hash 外部文件——已修。如果你看到这个，更新到 main 后重跑 | `runner.py` 现在 hash `--external-input` 内容；用 `--force` 兜底 |
| `author_editorial_rewrite` exit 1 + `WARNING: N internal tokens leaked` | redaction validator 抓到泄露 | 看 leak 列表；如果是新 stage/vendor 名，加进 `INTERNAL_TOKEN_PATTERNS` 并补 redaction 规则；不是绕过 |
| `methodology-adversary --provider claude` 报 `NotImplementedError` | Claude/OpenAI SDK 适配器是 stub | 用 `--provider manual` + `--external-input` 走人工 drop-off 路径 |
| `deepseek` provider 报 `DEEPSEEK_API_KEY is missing` | `config/secrets.local.env` 没设 | 写 key；或用 `--no-strong-model` 跑 offline fallback（质量会回到 V6 水平） |
| author 版没有 "### 隐藏假设与对照缺口" 子节 | 没跑 cross-provider secondary，或 merge 没产出 fatal/major | 检查 `methodology_adversary.merged.json` 的 hidden_assumptions 是否非空 |
| author 版 fatal 假设被译成 "请补充更详细描述" | rewrite prompt 被改弱了 | 回滚 `templates/prompts/author_editorial_rewrite.md` 到含 "禁止压平" clause 的版本 |

---

## 7. 一图概括

```text
DOCX/PDF
   │
   ▼ (human + MinerU)
normalized/manuscript.md + provenance/source_map.jsonl
   │
   ▼ (auto)
units/macro|chapters|sections + units/risk.json
   │
   ├──► paper_shape ──┐
   │                  │
   ▼                  │
deepseek_macro / chapters / sections  (cheap fanout)
   │                  │
   ▼                  │
issue_graph ──► detail_audit                meta_review_issues ◄── (strong)
   │                                              │
   │       ┌──────────────────────────────────────┤
   │       ▼                                      ▼
   │   methodology_adversary (deepseek primary)   review_comments.meta.json
   │       │
   │       │   methodology_adversary_secondary
   │       │   (manual provider; reads
   │       │   secondary_response.txt; first
   │       │   pass writes manual_pending stub +
   │       │   secondary_prompt.md to drop into
   │       │   external LLM)
   │       │
   │       ▼
   │   merge_methodology_adversaries (Sørensen-Dice + needs_human_decision)
   │       │
   │       ▼
   │   author_review_plan (force-merges fatal/major + claim_downgrade)
   │       │
   │       ▼
   │   author_editorial_rewrite ──► redaction validator ──► comments/author_facing_comments.md
   │                                                            │
   ▼                                                            ▼
human gates: claim_matrix_review, dissent, integrity_check,     送给作者
editorial_decision, retrospective
```

---

## 8. 更新这一份的时机

只有当下列之一为真时才更新本 runbook：

- 一个 stage 的命令行参数或位置参数变了；
- 默认 provider 或默认 voice 变了；
- 一个新的高杠杆 stage 加入主链（不是 fallback）；
- 一种新的反模式被实跑发现，并且已在 `docs/review_framework.md` 的 Anti-patterns 段记录。

不要在这里复述 `docs/review_framework.md` 的原则。原则的 single source of truth 在那里。本 runbook 只把原则变成可执行步骤。
