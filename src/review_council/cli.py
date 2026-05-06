"""Command-line interface for review-council."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_council.case.manifest import CASE_TYPES, CaseManifest
from review_council.case.paths import create_case, default_cases_root, repo_root
from review_council.case.validate import validate_case
from review_council.author_editorial import (
    DEFAULT_VOICE,
    VOICE_PROFILES,
    build_author_review_plan,
    run_author_editorial_rewrite,
)
from review_council.author_review import compose_author_review, polish_author_review
from review_council.claim_evidence import (
    DEFAULT_LINK_WINDOW,
    backfill_claim_anchors,
    link_issues_to_claims,
    render_claim_matrix_md,
)
from review_council.comments import render_comments
from review_council.comment_synthesis import DEFAULT_KEEP, synthesize_comments
from review_council.config import get_config_value
from review_council.detail_audit import build_detail_audit
from review_council.freeze import freeze_docx_to_pdf
from review_council.issue_graph import aggregate as aggregate_issue_graph
from review_council.meta_review import META_DEFAULT_MODEL, backfill_anchors, run_meta_review
from review_council.methodology_adversary import (
    DEFAULT_MODEL as METHODOLOGY_ADVERSARY_DEFAULT_MODEL,
    run_methodology_adversary,
)
from review_council.paper_shape import run_paper_shape
from review_council.prompts import render_prompt_template
from review_council.provenance import build_markdown_line_map
from review_council.provenance_pdf import build_pdf_page_map
from review_council.providers.deepseek import DEFAULT_BASE_URL, DEFAULT_MODEL, DeepSeekRequest, chat_completion
from review_council.rubrics import render_checks_block, select_rubrics
from review_council.runner import (
    StageResult,
    format_results_table,
    load_workflow,
    run_workflow,
    workflow_path_for,
)
from review_council.segment.risk import write_risk_table
from review_council.segment.units import build_hierarchical_units


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review-council")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_case = subparsers.add_parser("init-case", help="Create a review case scaffold")
    init_case.add_argument("case_id", help="Case identifier, e.g. demo_001")
    init_case.add_argument(
        "--cases-root",
        type=Path,
        default=default_cases_root(),
        help="Directory containing review cases",
    )
    init_case.add_argument("--title", default="", help="Optional manuscript title")
    init_case.add_argument("--case-type", default="journal", choices=CASE_TYPES)
    init_case.add_argument("--thesis-format", default="", help="monograph|cumulative; required for thesis_phd")
    init_case.add_argument("--discipline", default="", help="e.g. remote_sensing")

    validate = subparsers.add_parser("validate-case", help="Validate a review case")
    validate.add_argument("case_path", type=Path, help="Path to cases/<case-id>")

    index_markdown = subparsers.add_parser("index-markdown", help="Create a fallback line source map for Markdown")
    index_markdown.add_argument("markdown_path", type=Path)
    index_markdown.add_argument("source_map_path", type=Path)

    build_units = subparsers.add_parser("build-units", help="Create hierarchical review units from normalized Markdown")
    build_units.add_argument("markdown_path", type=Path)
    build_units.add_argument("units_root", type=Path)

    freeze_docx = subparsers.add_parser("freeze-docx", help="Freeze a DOCX manuscript into a PDF")
    freeze_docx.add_argument("docx_path", type=Path)
    freeze_docx.add_argument("output_pdf", type=Path)

    map_pdf_pages = subparsers.add_parser("map-pdf-pages", help="Add frozen-PDF page numbers to Markdown line anchors")
    map_pdf_pages.add_argument("markdown_path", type=Path)
    map_pdf_pages.add_argument("pdf_path", type=Path)
    map_pdf_pages.add_argument("source_map_path", type=Path)

    render = subparsers.add_parser("render-comments", help="Render review comments. --mode author hides provenance and sorts by revision_priority; --mode supervisor keeps full traceability.")
    render.add_argument("comments_path", type=Path)
    render.add_argument("source_map_path", type=Path)
    render.add_argument("output_path", type=Path)
    render.add_argument("--mode", choices=["author", "supervisor"], default="author")
    render.add_argument("--paper-shape", type=Path, default=None, help="Optional reviews/paper_shape.md to embed at top")
    render.add_argument("--show-provenance", action="store_true", help="Deprecated alias for --mode supervisor")
    render.add_argument("--locale", choices=["en", "zh"], default="en", help="Label language for priority/severity headings")
    render.add_argument("--hide-priority", action="store_true", help="Hide the Priority/优先级 label in author headings")

    paper_shape = subparsers.add_parser("paper-shape", help="Forced gestalt artifact: best version, current shape, top three transformation actions")
    paper_shape.add_argument("unit_path", type=Path, help="units/macro/whole.md")
    paper_shape.add_argument("output_path", type=Path, help="reviews/paper_shape.md")
    paper_shape.add_argument("--template", type=Path, default=Path("templates/prompts/paper_shape.md"))
    paper_shape.add_argument("--case-id", default="")
    paper_shape.add_argument("--case-type", default="journal", choices=CASE_TYPES)
    paper_shape.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    paper_shape.add_argument("--model", default=DEFAULT_MODEL)
    paper_shape.add_argument("--base-url", default=DEFAULT_BASE_URL)

    deepseek_review = subparsers.add_parser("deepseek-review-unit", help="Run a DeepSeek layered review prompt on one text unit")
    deepseek_review.add_argument("unit_path", type=Path)
    deepseek_review.add_argument("output_path", type=Path)
    deepseek_review.add_argument(
        "--template",
        type=Path,
        default=Path("templates/prompts/deepseek_local_review.md"),
        help="Prompt template path",
    )
    deepseek_review.add_argument("--case-id", default="", help="Review case id")
    deepseek_review.add_argument("--unit-id", default="", help="Review unit id")
    deepseek_review.add_argument("--layer", default="section", choices=["macro", "chapter", "section", "micro"])
    deepseek_review.add_argument("--case-type", default="journal", choices=CASE_TYPES)
    deepseek_review.add_argument("--rubrics-dir", type=Path, default=None, help="Defaults to <repo>/rubrics")
    deepseek_review.add_argument("--claims", type=Path, default=None, help="Optional evidence/claims_draft.json to ground section/chapter review on author claims")
    deepseek_review.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    deepseek_review.add_argument("--model", default=DEFAULT_MODEL)
    deepseek_review.add_argument("--base-url", default=DEFAULT_BASE_URL)
    deepseek_review.add_argument("--reasoning-effort", default=None)
    deepseek_review.add_argument("--thinking", choices=["enabled", "disabled"], default=None)

    list_rubrics = subparsers.add_parser("list-rubrics", help="Print applicable rubric checks for a (case_type, layer) pair")
    list_rubrics.add_argument("--case-type", default="journal", choices=CASE_TYPES)
    list_rubrics.add_argument("--layer", default="section", choices=["macro", "chapter", "section", "micro"])
    list_rubrics.add_argument("--rubrics-dir", type=Path, default=None)

    aggregate = subparsers.add_parser("aggregate-issue-graph", help="Aggregate per-unit DeepSeek reviews into reviews/issue_graph.json")
    aggregate.add_argument("deepseek_dir", type=Path, help="cases/<case-id>/reviews/deepseek")
    aggregate.add_argument("output_path", type=Path, help="cases/<case-id>/reviews/issue_graph.json")
    aggregate.add_argument("--case-id", default="")

    meta_review = subparsers.add_parser("meta-review-issues", help="Strong-model meta-review of an issue graph (cross-anchor dedup, severity recalibration, track assignment)")
    meta_review.add_argument("issue_graph_path", type=Path)
    meta_review.add_argument("output_review_md", type=Path)
    meta_review.add_argument("output_comments_json", type=Path)
    meta_review.add_argument("--draft", type=Path, default=None, help="comments/review_comments.draft.json")
    meta_review.add_argument("--claim-matrix", type=Path, default=None, help="evidence/claim_evidence_matrix.json")
    meta_review.add_argument("--template", type=Path, default=Path("templates/prompts/meta_reviewer.md"))
    meta_review.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    meta_review.add_argument("--model", default=META_DEFAULT_MODEL)
    meta_review.add_argument("--base-url", default=DEFAULT_BASE_URL)
    meta_review.add_argument("--top-n", type=int, default=80, help="Send the top-N severity-sorted issues to the strong model")
    meta_review.add_argument("--units-root", type=Path, default=None, help="Optional units/ root for chapter-level anchor backfill")
    meta_review.add_argument("--paper-shape", type=Path, default=None, help="Optional reviews/paper_shape.md gestalt anchor")

    backfill = subparsers.add_parser("backfill-comment-anchors", help="Fill missing line/page anchors in a comments JSON from issue_graph + units")
    backfill.add_argument("comments_path", type=Path)
    backfill.add_argument("issue_graph_path", type=Path)
    backfill.add_argument("--units-root", type=Path, default=None)

    synthesize = subparsers.add_parser("synthesize-comments", help="Synthesize a draft review_comments.json from reviews/issue_graph.json")
    synthesize.add_argument("issue_graph_path", type=Path, help="reviews/issue_graph.json")
    synthesize.add_argument("output_path", type=Path, help="comments/review_comments.draft.json")
    synthesize.add_argument("--claim-matrix", type=Path, default=None, help="Optional evidence/claim_evidence_matrix.json for linked_claims")
    synthesize.add_argument("--keep", default=",".join(DEFAULT_KEEP), help="Comma-separated severities to keep")

    detail_audit = subparsers.add_parser("detail-audit", help="Keep v1-style technical details as checklist items for author-review composition")
    detail_audit.add_argument("issue_graph_path", type=Path)
    detail_audit.add_argument("output_path", type=Path)
    detail_audit.add_argument("--max-items", type=int, default=36)

    compose_author = subparsers.add_parser("compose-author-review", help="Compose final author-facing review from paper_shape + strategic comments + detail audit")
    compose_author.add_argument("paper_shape_path", type=Path)
    compose_author.add_argument("strategic_comments_path", type=Path)
    compose_author.add_argument("detail_audit_path", type=Path)
    compose_author.add_argument("source_map_path", type=Path)
    compose_author.add_argument("output_md_path", type=Path)
    compose_author.add_argument("--output-json", type=Path, default=None)

    author_polish = subparsers.add_parser("author-polish", help="Clean process/provenance language from an author-facing Markdown review")
    author_polish.add_argument("input_md_path", type=Path)
    author_polish.add_argument("output_md_path", type=Path)

    voices = sorted(VOICE_PROFILES.keys())

    plan = subparsers.add_parser(
        "author-review-plan",
        help="Editorial planning step. Decides best form, 3 directions, must-keep strategic comments, detail pool, demote/drop.",
    )
    plan.add_argument("paper_shape_path", type=Path)
    plan.add_argument("meta_comments_path", type=Path)
    plan.add_argument("detail_audit_path", type=Path)
    plan.add_argument("output_json_path", type=Path)
    plan.add_argument("output_md_path", type=Path)
    plan.add_argument("--voice", choices=voices, default=DEFAULT_VOICE)
    plan.add_argument("--template", type=Path, default=Path("templates/prompts/author_review_plan.md"))
    plan.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    plan.add_argument("--model", default=META_DEFAULT_MODEL)
    plan.add_argument("--base-url", default=DEFAULT_BASE_URL)
    plan.add_argument("--no-strong-model", action="store_true", help="Skip the strong model and use the offline fallback")
    plan.add_argument(
        "--methodology-adversary",
        type=Path,
        default=None,
        help="Optional reviews/methodology_adversary.json (or .merged.json); fatal/major findings are force-merged into must_keep_strategic, and merged inputs additionally pipe needs_human_decision through to the plan",
    )

    adversary = subparsers.add_parser(
        "methodology-adversary",
        help="Adversarial methodology audit. Reads intro+methods+results, emits hidden_assumptions + unmet_research_goals JSON for plan to consume.",
    )
    adversary.add_argument("intro_path", type=Path, help="units/chapters/chapter_01.md")
    adversary.add_argument("methods_path", type=Path, help="units/chapters/chapter_03.md")
    adversary.add_argument("results_path", type=Path, help="units/chapters/chapter_04.md")
    adversary.add_argument("output_path", type=Path, help="reviews/methodology_adversary.json")
    adversary.add_argument("--template", type=Path, default=Path("templates/prompts/methodology_adversary.md"))
    adversary.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    adversary.add_argument("--model", default=METHODOLOGY_ADVERSARY_DEFAULT_MODEL)
    adversary.add_argument("--base-url", default=DEFAULT_BASE_URL)
    adversary.add_argument("--case-id", default="")
    adversary.add_argument("--no-strong-model", action="store_true", help="Write an offline stub instead of calling the strong model")
    adversary.add_argument("--provider", default="deepseek", help="Provider name from the registry (deepseek|claude|openai|gpt|manual|external_file)")
    adversary.add_argument("--n-runs", type=int, default=1, help="Run the prompt N times at varied temperature; top-level lists are deduped across runs")
    adversary.add_argument("--temperature", type=float, default=0.2, help="Base temperature; multi-run adds 0.1 per additional run")
    adversary.add_argument("--external-input", type=Path, default=None, help="For --provider manual: path to a file containing the LLM response (created externally)")
    adversary.add_argument("--prompt-cache", type=Path, default=None, help="For --provider manual: where to write the rendered prompt when the response file is missing")
    adversary.add_argument("--skip-if-missing", action="store_true", help="For --provider manual: when external response is missing, write a manual_pending stub and exit 0 (instead of erroring)")

    merge_adv = subparsers.add_parser(
        "merge-methodology-adversaries",
        help="Merge multiple methodology_adversary JSON files (e.g. one per provider/run) into a unified report with agreement classification and human-decision flags.",
    )
    merge_adv.add_argument("output_path", type=Path, help="reviews/methodology_adversary.merged.json")
    merge_adv.add_argument("--input", action="append", default=[], type=Path, help="Adversary JSON to merge (repeat). Missing files are skipped.")
    merge_adv.add_argument("--md", type=Path, default=None, help="Optional Markdown rendering of the merged report")
    merge_adv.add_argument("--similarity-threshold", type=float, default=None, help="Sørensen–Dice threshold for grouping near-duplicate findings (default: 0.3)")

    rewrite = subparsers.add_parser(
        "author-editorial-rewrite",
        help="Strong-model rewrite of the author-facing review using the editorial plan. Falls back to deterministic compose+polish offline.",
    )
    rewrite.add_argument("paper_shape_path", type=Path)
    rewrite.add_argument("plan_path", type=Path)
    rewrite.add_argument("meta_comments_path", type=Path)
    rewrite.add_argument("detail_audit_path", type=Path)
    rewrite.add_argument("source_map_path", type=Path)
    rewrite.add_argument("output_md_path", type=Path)
    rewrite.add_argument("--voice", choices=voices, default=DEFAULT_VOICE)
    rewrite.add_argument("--template", type=Path, default=Path("templates/prompts/author_editorial_rewrite.md"))
    rewrite.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    rewrite.add_argument("--model", default=META_DEFAULT_MODEL)
    rewrite.add_argument("--base-url", default=DEFAULT_BASE_URL)
    rewrite.add_argument("--no-strong-model", action="store_true", help="Skip the strong model and use the offline fallback")
    rewrite.add_argument("--provider", default="deepseek", help="Provider name from the registry (deepseek|claude|openai|gpt|manual|external_file)")
    rewrite.add_argument("--external-input", type=Path, default=None, help="For --provider manual: path to a file containing the externally-generated rewrite Markdown")
    rewrite.add_argument("--prompt-cache", type=Path, default=None, help="For --provider manual: where to write the rendered prompt when the response file is missing")

    extract_claims = subparsers.add_parser("extract-claims", help="DeepSeek-extract author claims from a unit into a CLM draft JSON")
    extract_claims.add_argument("unit_path", type=Path)
    extract_claims.add_argument("output_path", type=Path)
    extract_claims.add_argument("--template", type=Path, default=Path("templates/prompts/extract_claims.md"))
    extract_claims.add_argument("--case-id", default="")
    extract_claims.add_argument("--case-type", default="journal", choices=CASE_TYPES)
    extract_claims.add_argument("--unit-id", default="")
    extract_claims.add_argument("--config", type=Path, default=Path("config/secrets.local.env"))
    extract_claims.add_argument("--model", default=DEFAULT_MODEL)
    extract_claims.add_argument("--base-url", default=DEFAULT_BASE_URL)
    extract_claims.add_argument(
        "--no-backfill-anchors",
        action="store_true",
        help="Skip text-match anchor backfill on the resulting claims_draft.json",
    )

    backfill_claims = subparsers.add_parser(
        "backfill-claim-anchors",
        help="Backfill missing line anchors in evidence/claims_draft.json by matching claim text to the unit",
    )
    backfill_claims.add_argument("claims_path", type=Path)
    backfill_claims.add_argument("unit_path", type=Path)

    link_claims = subparsers.add_parser("link-issues-to-claims", help="Heuristically link reviews/issue_graph.json issues to evidence/claim_evidence_matrix.json claims by anchor proximity")
    link_claims.add_argument("claim_matrix_path", type=Path, help="evidence/claim_evidence_matrix.json")
    link_claims.add_argument("issue_graph_path", type=Path, help="reviews/issue_graph.json")
    link_claims.add_argument("--link-window", type=int, default=DEFAULT_LINK_WINDOW, help="Lines of slack on each side")
    link_claims.add_argument("--overwrite", action="store_true", help="Replace existing linked_issues instead of merging")

    render_matrix = subparsers.add_parser("render-claim-matrix", help="Render evidence/claim_evidence_matrix.json to a Markdown view")
    render_matrix.add_argument("claim_matrix_path", type=Path)
    render_matrix.add_argument("output_path", type=Path)
    render_matrix.add_argument("--issue-graph", type=Path, default=None, help="Optional reviews/issue_graph.json for issue context in the rendered view")

    score_risk = subparsers.add_parser("score-section-risk", help="Recompute units/risk.json from existing review units")
    score_risk.add_argument("units_root", type=Path, help="cases/<case-id>/units")
    score_risk.add_argument("--output", type=Path, default=None, help="Defaults to <units_root>/risk.json")

    review_case = subparsers.add_parser("review-case", help="Run the workflow recipe for a case end-to-end (idempotent)")
    review_case.add_argument("case_path", type=Path, help="Path to cases/<case-id>")
    review_case.add_argument("--workflows-dir", type=Path, default=None, help="Defaults to <repo>/docs/workflows")
    review_case.add_argument("--force", action="store_true", help="Re-run stages even when outputs exist")
    review_case.add_argument("--only", default="", help="Comma-separated stage ids to run; others reported as not_selected")
    review_case.add_argument("--until", default="", help="Stop after running this stage id")
    review_case.add_argument("--list", action="store_true", help="Print stages and exit without running")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-case":
        manifest = CaseManifest(
            case_id=args.case_id,
            title=args.title,
            case_type=args.case_type,
            thesis_format=args.thesis_format,
            discipline=args.discipline,
        )
        case_path = create_case(args.case_id, args.cases_root, manifest)
        print(case_path)
        return 0

    if args.command == "validate-case":
        result = validate_case(args.case_path)
        if result.errors:
            for error in result.errors:
                print(f"ERROR: {error}")
            return 1
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        print("OK")
        return 0

    if args.command == "index-markdown":
        anchors = build_markdown_line_map(args.markdown_path, args.source_map_path)
        print(f"{len(anchors)} anchors")
        return 0

    if args.command == "build-units":
        units = build_hierarchical_units(args.markdown_path, args.units_root)
        print(f"{len(units)} units")
        return 0

    if args.command == "freeze-docx":
        output_pdf = freeze_docx_to_pdf(args.docx_path, args.output_pdf)
        print(output_pdf)
        return 0

    if args.command == "map-pdf-pages":
        anchors = build_pdf_page_map(args.markdown_path, args.pdf_path, args.source_map_path)
        mapped = sum(1 for anchor in anchors if anchor.source_page)
        print(f"{mapped}/{len(anchors)} anchors mapped to PDF pages")
        return 0

    if args.command == "render-comments":
        mode = "supervisor" if args.show_provenance else args.mode
        render_comments(
            args.comments_path,
            args.source_map_path,
            args.output_path,
            mode=mode,
            paper_shape_path=args.paper_shape,
            locale=args.locale,
            hide_priority=args.hide_priority,
        )
        print(args.output_path)
        return 0

    if args.command == "paper-shape":
        api_key = get_config_value("DEEPSEEK_API_KEY", args.config)
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY is missing from environment or local config")
            return 1
        path = run_paper_shape(
            unit_path=args.unit_path,
            output_path=args.output_path,
            prompt_template=args.template,
            api_key=api_key,
            case_id=args.case_id,
            case_type=args.case_type,
            model=args.model,
            base_url=args.base_url,
        )
        print(path)
        return 0

    if args.command == "list-rubrics":
        rubrics_dir = args.rubrics_dir or (repo_root() / "rubrics")
        rubrics = select_rubrics(rubrics_dir, args.case_type, _layer_alias(args.layer))
        print(render_checks_block(rubrics) or "(no applicable rubrics)")
        return 0

    if args.command == "meta-review-issues":
        api_key = get_config_value("DEEPSEEK_API_KEY", args.config)
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY is missing from environment or local config")
            return 1
        stats = run_meta_review(
            issue_graph_path=args.issue_graph_path,
            output_review_md=args.output_review_md,
            output_comments_json=args.output_comments_json,
            prompt_template=args.template,
            api_key=api_key,
            draft_path=args.draft,
            claim_matrix_path=args.claim_matrix,
            paper_shape_path=args.paper_shape,
            units_root=args.units_root,
            model=args.model,
            base_url=args.base_url,
            top_n_issues=args.top_n,
        )
        print(
            f"{stats['output_comments']} comments from {stats['considered_issues']} considered issues "
            f"(of {stats['input_issues']}); {stats['anchors_backfilled']} anchors backfilled "
            f"-> {stats['comments_json']}"
        )
        return 0

    if args.command == "backfill-comment-anchors":
        comments = json.loads(args.comments_path.read_text(encoding="utf-8"))
        graph = json.loads(args.issue_graph_path.read_text(encoding="utf-8"))
        issues = graph.get("issues", []) if isinstance(graph, dict) else []
        n = backfill_anchors(comments, issues, units_root=args.units_root)
        args.comments_path.write_text(
            json.dumps(comments, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"{n} anchors backfilled in {args.comments_path}")
        return 0

    if args.command == "synthesize-comments":
        keep = tuple(s.strip() for s in args.keep.split(",") if s.strip())
        stats = synthesize_comments(
            args.issue_graph_path,
            args.output_path,
            claim_matrix_path=args.claim_matrix,
            keep_severities=keep,
        )
        print(f"{stats['kept_comments']} comments synthesized from {stats['input_issues']} issues -> {args.output_path}")
        return 0

    if args.command == "detail-audit":
        stats = build_detail_audit(
            args.issue_graph_path,
            args.output_path,
            max_items=args.max_items,
        )
        print(f"{stats['detail_items']} detail items from {stats['input_issues']} issues -> {args.output_path}")
        return 0

    if args.command == "compose-author-review":
        stats = compose_author_review(
            paper_shape_path=args.paper_shape_path,
            strategic_comments_path=args.strategic_comments_path,
            detail_audit_path=args.detail_audit_path,
            source_map_path=args.source_map_path,
            output_md_path=args.output_md_path,
            output_json_path=args.output_json,
        )
        print(
            f"{stats['strategic_comments']} strategic comments + {stats['detail_items']} detail items "
            f"-> {stats['output']}"
        )
        return 0

    if args.command == "author-polish":
        stats = polish_author_review(args.input_md_path, args.output_md_path)
        print(f"{stats['chars']} chars -> {stats['output']}")
        return 0

    if args.command == "author-review-plan":
        api_key = None if args.no_strong_model else get_config_value("DEEPSEEK_API_KEY", args.config)
        stats = build_author_review_plan(
            paper_shape_path=args.paper_shape_path,
            meta_comments_path=args.meta_comments_path,
            detail_audit_path=args.detail_audit_path,
            output_json_path=args.output_json_path,
            output_md_path=args.output_md_path,
            voice=args.voice,
            api_key=api_key or None,
            prompt_template=args.template,
            model=args.model,
            base_url=args.base_url,
            methodology_adversary_path=args.methodology_adversary,
        )
        print(
            f"plan source={stats['source']} voice={stats['voice']} "
            f"must_keep={stats['must_keep']} detail_pool={stats['detail_pool']} -> {stats['output_json']}"
        )
        return 0

    if args.command == "methodology-adversary":
        api_key = None if args.no_strong_model else get_config_value("DEEPSEEK_API_KEY", args.config)
        stats = run_methodology_adversary(
            intro_path=args.intro_path,
            methods_path=args.methods_path,
            results_path=args.results_path,
            output_path=args.output_path,
            prompt_template=args.template,
            api_key=api_key or None,
            model=args.model,
            base_url=args.base_url,
            case_id=args.case_id,
            provider=args.provider,
            n_runs=args.n_runs,
            temperature=args.temperature,
            external_input=args.external_input,
            prompt_cache=args.prompt_cache,
            skip_if_missing=args.skip_if_missing,
        )
        print(
            f"adversary provider={stats['provider']} source={stats['source']} "
            f"runs={stats['n_runs']} fatal={stats['fatal']} major={stats['major']} "
            f"moderate={stats['moderate']} unmet_goals={stats['unmet_goals']} -> {stats['output']}"
        )
        return 0

    if args.command == "merge-methodology-adversaries":
        from review_council.adversary_merge import merge_adversaries

        if not args.input:
            print("ERROR: at least one --input is required")
            return 1
        from review_council.adversary_merge import DEFAULT_SIMILARITY

        merged = merge_adversaries(
            args.input,
            args.output_path,
            similarity_threshold=args.similarity_threshold if args.similarity_threshold is not None else DEFAULT_SIMILARITY,
            md_output_path=args.md,
        )
        print(
            f"merged providers={','.join(merged.get('providers') or []) or '(none)'} "
            f"runs={merged.get('n_total_runs', 0)} "
            f"hidden_assumptions={len(merged.get('hidden_assumptions') or [])} "
            f"unmet_goals={len(merged.get('unmet_research_goals') or [])} "
            f"claim_dependencies={len(merged.get('headline_claim_dependencies') or [])} "
            f"needs_human={len(merged.get('needs_human_decision') or [])} "
            f"skipped={len(merged.get('skipped_inputs') or [])} -> {args.output_path}"
        )
        return 0

    if args.command == "author-editorial-rewrite":
        api_key = None if args.no_strong_model else get_config_value("DEEPSEEK_API_KEY", args.config)
        try:
            stats = run_author_editorial_rewrite(
                paper_shape_path=args.paper_shape_path,
                plan_path=args.plan_path,
                meta_comments_path=args.meta_comments_path,
                detail_audit_path=args.detail_audit_path,
                source_map_path=args.source_map_path,
                output_md_path=args.output_md_path,
                voice=args.voice,
                api_key=api_key or None,
                prompt_template=args.template,
                model=args.model,
                base_url=args.base_url,
                provider=args.provider,
                external_input=args.external_input,
                prompt_cache=args.prompt_cache,
            )
        except Exception as exc:  # noqa: BLE001
            # Manual provider with no external response yet — surface the
            # actionable error and exit non-zero so the workflow stops cleanly.
            from review_council.providers.manual_provider import ManualPendingError

            if isinstance(exc, ManualPendingError):
                print(f"PENDING: {exc}")
                return 2
            raise
        rc = 0
        if stats["leaks"]:
            print(f"WARNING: {len(stats['leaks'])} internal tokens leaked: {stats['leaks'][:5]}")
            rc = 1
        print(
            f"rewrite provider={stats['provider']} voice={stats['voice']} "
            f"used_strong={stats['used_strong']} chars={stats['chars']} -> {stats['output']}"
        )
        return rc

    if args.command == "score-section-risk":
        path = write_risk_table(args.units_root, args.output)
        print(path)
        return 0

    if args.command == "extract-claims":
        api_key = get_config_value("DEEPSEEK_API_KEY", args.config)
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY is missing from environment or local config")
            return 1
        unit_text = args.unit_path.read_text(encoding="utf-8")
        prompt = render_prompt_template(
            args.template,
            {
                "case_id": args.case_id,
                "case_type": args.case_type,
                "unit_id": args.unit_id or args.unit_path.stem,
            },
        )
        prompt = prompt.rstrip() + "\n\n[Supplied unit text]\n" + unit_text
        response = chat_completion(
            DeepSeekRequest(
                api_key=api_key,
                prompt=prompt,
                model=args.model,
                base_url=args.base_url,
            )
        )
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(response.rstrip() + "\n", encoding="utf-8")
        if not args.no_backfill_anchors:
            try:
                stats = backfill_claim_anchors(args.output_path, args.unit_path)
                print(
                    f"{args.output_path}  ({stats['backfilled']}/{stats['claims']} anchors backfilled)"
                )
                return 0
            except (json.JSONDecodeError, OSError) as exc:
                print(f"WARNING: anchor backfill failed: {exc}")
        print(args.output_path)
        return 0

    if args.command == "backfill-claim-anchors":
        stats = backfill_claim_anchors(args.claims_path, args.unit_path)
        print(f"{stats['backfilled']}/{stats['claims']} anchors backfilled in {args.claims_path}")
        return 0

    if args.command == "link-issues-to-claims":
        stats = link_issues_to_claims(
            args.claim_matrix_path,
            args.issue_graph_path,
            link_window=args.link_window,
            overwrite=args.overwrite,
        )
        print(f"{stats['claims']} claims, {stats['links_added']} new links (window={args.link_window})")
        return 0

    if args.command == "render-claim-matrix":
        path = render_claim_matrix_md(args.claim_matrix_path, args.output_path, args.issue_graph)
        print(path)
        return 0

    if args.command == "aggregate-issue-graph":
        graph = aggregate_issue_graph(args.deepseek_dir, args.output_path, args.case_id)
        print(f"{len(graph['issues'])} issues, {len(graph['clusters'])} cluster candidates -> {args.output_path}")
        return 0

    if args.command == "review-case":
        workflows_dir = args.workflows_dir or (repo_root() / "docs" / "workflows")
        manifest_path = args.case_path / "manifest.yaml"
        if not manifest_path.is_file():
            print(f"ERROR: manifest not found: {manifest_path}")
            return 1
        case_type = _read_case_type(manifest_path)
        if not case_type:
            print("ERROR: manifest.yaml has no case_type")
            return 1
        path = workflow_path_for(case_type, workflows_dir)
        if not path.is_file():
            print(f"ERROR: workflow not found for case_type={case_type}: {path}")
            return 1
        workflow = load_workflow(path)
        if args.list:
            for stage in workflow.stages:
                gate = " (gate: human)" if stage.gate == "human" else ""
                print(f"{stage.id}{gate}: {stage.description}")
            return 0
        only = {s.strip() for s in args.only.split(",") if s.strip()} or None
        results = run_workflow(
            args.case_path,
            workflow,
            main,
            force=args.force,
            only=only,
            until=args.until or None,
        )
        print(format_results_table(results))
        return 0 if not any(r.status in {"error", "partial"} for r in results) else 1

    if args.command == "deepseek-review-unit":
        api_key = get_config_value("DEEPSEEK_API_KEY", args.config)
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY is missing from environment or local config")
            return 1
        unit_text = args.unit_path.read_text(encoding="utf-8")
        rubrics_dir = args.rubrics_dir or (repo_root() / "rubrics")
        rubrics = select_rubrics(rubrics_dir, args.case_type, _layer_alias(args.layer))
        rubric_block = render_checks_block(rubrics) or "(no applicable rubric checks for this layer)"
        claim_block = "(no claim draft supplied)"
        if args.claims and args.claims.exists():
            try:
                claims_data = json.loads(args.claims.read_text(encoding="utf-8"))
                claims_list = claims_data.get("claims", []) if isinstance(claims_data, dict) else []
                if claims_list:
                    lines = []
                    for claim in claims_list[:30]:
                        cid = claim.get("id", "?")
                        ctype = claim.get("type", "?")
                        ctext = (claim.get("text") or "").strip().replace("\n", " ")
                        if len(ctext) > 160:
                            ctext = ctext[:157] + "..."
                        lines.append(f"- [{cid}] ({ctype}) {ctext}")
                    claim_block = "\n".join(lines)
            except (json.JSONDecodeError, OSError):
                pass
        prompt = render_prompt_template(
            args.template,
            {
                "case_id": args.case_id,
                "case_type": args.case_type,
                "unit_id": args.unit_id or args.unit_path.stem,
                "layer": args.layer,
                "rubric_checks": rubric_block,
                "claim_context": claim_block,
            },
        )
        prompt = prompt.rstrip() + "\n\n[Supplied unit text]\n" + unit_text
        response = chat_completion(
            DeepSeekRequest(
                api_key=api_key,
                prompt=prompt,
                model=args.model,
                base_url=args.base_url,
                reasoning_effort=args.reasoning_effort,
                thinking=None if args.thinking is None else args.thinking == "enabled",
            )
        )
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(response.rstrip() + "\n", encoding="utf-8")
        print(args.output_path)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _layer_alias(layer: str) -> str:
    aliases = {"chapters": "chapter", "sections": "section"}
    return aliases.get(layer, layer)


def _read_case_type(manifest_path: Path) -> str:
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("case_type:"):
            return line.partition(":")[2].strip().strip("'\"")
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
