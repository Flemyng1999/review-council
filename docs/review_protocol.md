# Review Protocol

## Flow

1. Create a case directory with `review-council init-case <case-id>`.
2. Place manuscript files under `source/`.
3. Normalize source files into `normalized/`.
4. Generate `provenance/source_map.jsonl`.
5. Split the normalized manuscript into reviewable units under `units/`.
6. Extract claims and evidence anchors into `evidence/`.
7. Record structured comments under `comments/review_comments.json`.
8. Run role-specific reviews under `reviews/`.
9. Synthesize disagreements without erasing dissent.
10. Render author-facing comments with page/line anchors under `comments/`.
11. Record human editorial judgment under `decision/`.
12. Write a retrospective after the review closes.

## Roles

- Human editor: owns scope, final judgment, and accountability.
- Primary reviewer: identifies main strengths, weaknesses, and revision needs.
- Verifier: checks factual, methodological, and citation claims.
- Dissent reviewer: argues against emerging consensus and names uncertainty.
- Evidence clerk: maintains claim-to-source traceability.

## Invariant

Critique can be AI-assisted. Judgment is human-owned.
