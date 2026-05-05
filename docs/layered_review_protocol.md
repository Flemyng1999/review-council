# Layered Review Protocol

Purpose: make review a structured creative analysis, not a flat checklist.

## Core Idea

A manuscript must be reviewed at multiple granularities because each layer
reveals different truths.

- **Whole-paper layer**: idea, contribution, completion, story, scientific
  proportionality, target fit.
- **Chapter/section layer**: whether each part performs its role in the whole
  argument.
- **Local evidence layer**: equations, data, methods, validation, figures,
  citations, units, and claim-evidence links.
- **Micro layer**: wording, formatting, typos, ambiguous terminology, and
  author-facing clarity.

The workflow must preserve all layers and then synthesize them. A local flaw is
not automatically a fatal flaw; a smooth whole story does not excuse local
method failure.

## AI Division of Labor

DeepSeek is used heavily for coverage:

- whole-manuscript creative reading;
- chapter role review;
- section/local evidence review;
- issue extraction into structured JSON;
- repeated dissent or alternative-reading passes.

The stronger model is used for compression-resistant judgment:

- deleting weak comments;
- upgrading serious issues;
- detecting cross-layer contradictions;
- writing the final AI synthesis for human review.

The human reviewer owns the final decision.

## Fixed Artifacts

```text
units/macro/whole.md
units/chapters/chapter_*.md
units/sections/section_*.md
reviews/deepseek/<layer>/<unit>.json
reviews/hierarchical_review.md
reviews/meta_review.md
comments/review_comments.json
comments/author_facing_comments.md
```

## Workflow

1. Build normalized Markdown and frozen-PDF page map.
2. Build hierarchical review units.
3. Run DeepSeek on macro, chapter, and high-risk section units.
4. Merge DeepSeek outputs into an issue graph.
5. Run strong meta-review over the issue graph plus selected anchors.
6. Render author-facing comments with PDF page anchors.
7. Human reviewer edits and approves final feedback.

## Acceptance Standard

A review is not complete until it answers:

- What is the best possible version of this paper?
- What is the actual current shape of the paper?
- Which issues block that transformation?
- Which comments are useful to the author rather than merely critical?
- Which judgments require human responsibility?
