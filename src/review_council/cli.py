"""Command-line interface for review-council."""

from __future__ import annotations

import argparse
from pathlib import Path

from review_council.case.manifest import CASE_TYPES, CaseManifest
from review_council.case.paths import create_case, default_cases_root, repo_root
from review_council.case.validate import validate_case
from review_council.claim_evidence import (
    DEFAULT_LINK_WINDOW,
    link_issues_to_claims,
    render_claim_matrix_md,
)
from review_council.comments import render_comments
from review_council.comment_synthesis import DEFAULT_KEEP, synthesize_comments
from review_council.config import get_config_value
from review_council.freeze import freeze_docx_to_pdf
from review_council.issue_graph import aggregate as aggregate_issue_graph
from review_council.meta_review import META_DEFAULT_MODEL, run_meta_review
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

    render = subparsers.add_parser("render-comments", help="Render author-facing comments with page/line anchors")
    render.add_argument("comments_path", type=Path)
    render.add_argument("source_map_path", type=Path)
    render.add_argument("output_path", type=Path)

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

    synthesize = subparsers.add_parser("synthesize-comments", help="Synthesize a draft review_comments.json from reviews/issue_graph.json")
    synthesize.add_argument("issue_graph_path", type=Path, help="reviews/issue_graph.json")
    synthesize.add_argument("output_path", type=Path, help="comments/review_comments.draft.json")
    synthesize.add_argument("--claim-matrix", type=Path, default=None, help="Optional evidence/claim_evidence_matrix.json for linked_claims")
    synthesize.add_argument("--keep", default=",".join(DEFAULT_KEEP), help="Comma-separated severities to keep")

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
        render_comments(args.comments_path, args.source_map_path, args.output_path)
        print(args.output_path)
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
            model=args.model,
            base_url=args.base_url,
            top_n_issues=args.top_n,
        )
        print(
            f"{stats['output_comments']} comments from {stats['considered_issues']} considered issues "
            f"(of {stats['input_issues']}) -> {stats['comments_json']}"
        )
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
        print(args.output_path)
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
        return 0 if not any(r.status == "error" for r in results) else 1

    if args.command == "deepseek-review-unit":
        api_key = get_config_value("DEEPSEEK_API_KEY", args.config)
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY is missing from environment or local config")
            return 1
        unit_text = args.unit_path.read_text(encoding="utf-8")
        rubrics_dir = args.rubrics_dir or (repo_root() / "rubrics")
        rubrics = select_rubrics(rubrics_dir, args.case_type, _layer_alias(args.layer))
        rubric_block = render_checks_block(rubrics) or "(no applicable rubric checks for this layer)"
        prompt = render_prompt_template(
            args.template,
            {
                "case_id": args.case_id,
                "case_type": args.case_type,
                "unit_id": args.unit_id or args.unit_path.stem,
                "layer": args.layer,
                "rubric_checks": rubric_block,
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
