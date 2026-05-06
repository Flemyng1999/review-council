import json
from pathlib import Path

import pytest

from review_council.case.manifest import CaseManifest
from review_council.case.paths import create_case
from review_council.case.validate import validate_case
from review_council.author_review import compose_author_review, polish_author_review
from review_council.comments import render_comments
from review_council.config import get_config_value, load_env_file
from review_council.detail_audit import build_detail_audit
from review_council.issue_graph import aggregate as aggregate_issue_graph
from review_council.prompts import render_prompt_template
from review_council.provenance import build_markdown_line_map
from review_council.provenance_pdf import build_pdf_page_map
from review_council.rubrics import (
    DIMENSIONS,
    parse_rubric,
    render_checks_block,
    select_rubrics,
)
from review_council.claim_evidence import (
    Claim,
    ClaimAnchor,
    EvidenceAnchor,
    backfill_claim_anchors,
    link_issues_to_claims,
    load_claim_matrix,
    render_claim_matrix_md,
    save_claim_matrix,
)
from review_council.comment_synthesis import _apply_severity_caps, synthesize_comments
from review_council.meta_review import backfill_anchors, split_meta_review_response
from review_council.providers.deepseek import DeepSeekRequest, chat_completion
from review_council.runner import load_workflow, run_workflow
from review_council.segment.risk import (
    compute_risk_table,
    load_risk_table,
    score_text,
    write_risk_table,
)
from review_council.segment.sections import split_markdown_sections
from review_council.segment.units import build_hierarchical_units


REPO_ROOT = Path(__file__).resolve().parents[1]
RUBRICS_DIR = REPO_ROOT / "rubrics"


def test_create_case_and_validate(tmp_path: Path) -> None:
    case_path = create_case("demo_001", tmp_path, CaseManifest(case_id="demo_001"))

    result = validate_case(case_path)

    assert result.ok
    assert "source/ contains no manuscript files" in result.warnings
    assert (case_path / "source" / "supplementary").is_dir()
    assert (case_path / "evidence" / "claim_evidence_matrix.json").is_file()
    assert (case_path / "decision" / "editorial_judgment.md").is_file()


def test_default_case_type_is_journal(tmp_path: Path) -> None:
    case_path = create_case("demo_journal", tmp_path, CaseManifest(case_id="demo_journal"))
    text = (case_path / "manifest.yaml").read_text(encoding="utf-8")
    assert "case_type: journal" in text


def test_thesis_phd_requires_format() -> None:
    with pytest.raises(ValueError):
        CaseManifest(case_id="phd_no_format", case_type="thesis_phd")


def test_thesis_phd_with_format_passes(tmp_path: Path) -> None:
    manifest = CaseManifest(case_id="phd_mono", case_type="thesis_phd", thesis_format="monograph")
    case_path = create_case("phd_mono", tmp_path, manifest)
    text = (case_path / "manifest.yaml").read_text(encoding="utf-8")
    assert "case_type: thesis_phd" in text
    assert "thesis_format: monograph" in text
    assert validate_case(case_path).ok


def test_unknown_case_type_rejected() -> None:
    with pytest.raises(ValueError):
        CaseManifest(case_id="bad", case_type="thesis_postdoc")


def test_split_markdown_sections() -> None:
    sections = split_markdown_sections("# A\none\n## B\ntwo\n")

    assert sections == ["# A\none", "## B\ntwo"]


def test_render_comments_with_markdown_line_map(tmp_path: Path) -> None:
    manuscript = tmp_path / "manuscript.md"
    source_map = tmp_path / "source_map.jsonl"
    comments = tmp_path / "comments.json"
    output = tmp_path / "author_comments.md"

    manuscript.write_text("# Title\n\nUnsupported claim.\n", encoding="utf-8")
    build_markdown_line_map(manuscript, source_map)
    comments.write_text(
        """
[
  {
    "id": "CMT-001",
    "severity": "major",
    "anchor_id": "L00003",
    "quote": "",
    "comment": "This claim needs evidence.",
    "recommendation": "Add data or narrow the claim."
  }
]
""".strip(),
        encoding="utf-8",
    )

    render_comments(comments, source_map, output)

    rendered = output.read_text(encoding="utf-8")
    assert "p. ?, normalized line 3" in rendered
    assert "Unsupported claim." in rendered
    assert "This claim needs evidence." in rendered


def test_build_pdf_page_map(tmp_path: Path) -> None:
    try:
        import fitz
    except ImportError:
        return

    pdf_path = tmp_path / "frozen.pdf"
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Title\nFirst page claim")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Second page method")
    doc.save(pdf_path)
    doc.close()

    manuscript = tmp_path / "manuscript.md"
    source_map = tmp_path / "source_map.jsonl"
    manuscript.write_text("# Title\n\nFirst page claim\n\nSecond page method\n", encoding="utf-8")

    anchors = build_pdf_page_map(manuscript, pdf_path, source_map)

    pages = {anchor.anchor_id: anchor.source_page for anchor in anchors}
    assert pages["L00003"] == 1
    assert pages["L00005"] == 2


def test_load_local_config_without_network(tmp_path: Path) -> None:
    config = tmp_path / "secrets.local.env"
    config.write_text("DEEPSEEK_API_KEY=test-key\n", encoding="utf-8")

    assert load_env_file(config)["DEEPSEEK_API_KEY"] == "test-key"
    assert get_config_value("DEEPSEEK_API_KEY", config) == "test-key"


def test_render_prompt_template(tmp_path: Path) -> None:
    template = tmp_path / "prompt.md"
    template.write_text("case={case_id}; unit={unit_id}", encoding="utf-8")

    rendered = render_prompt_template(template, {"case_id": "c1", "unit_id": "u1"})

    assert rendered == "case=c1; unit=u1"


def test_render_prompt_template_strips_frontmatter(tmp_path: Path) -> None:
    template = tmp_path / "with_frontmatter.md"
    template.write_text("---\nname: x\n---\nbody {case_id}\n", encoding="utf-8")

    rendered = render_prompt_template(template, {"case_id": "c1"})

    assert rendered.strip() == "body c1"


def test_build_hierarchical_units(tmp_path: Path) -> None:
    manuscript = tmp_path / "manuscript.md"
    units_root = tmp_path / "units"
    manuscript.write_text("# Ch1\nA\n## S1\nB\n# Ch2\nC\n", encoding="utf-8")

    units = build_hierarchical_units(manuscript, units_root)

    assert (units_root / "macro" / "whole.md").is_file()
    assert (units_root / "chapters" / "chapter_01.md").is_file()
    assert (units_root / "sections" / "section_01.md").is_file()
    assert len(units) == 4


def test_methodology_rubric_has_frontmatter() -> None:
    rubric = parse_rubric(RUBRICS_DIR / "methodology.md")

    assert rubric.dimension == "methodology"
    assert "section" in rubric.applicable_layers
    assert any(check.id.startswith("MET-") for check in rubric.checks)


def test_select_rubrics_filters_by_case_type() -> None:
    journal = select_rubrics(RUBRICS_DIR, case_type="journal", layer="macro")
    undergrad = select_rubrics(RUBRICS_DIR, case_type="thesis_undergrad", layer="macro")

    journal_dims = {r.dimension for r in journal}
    undergrad_dims = {r.dimension for r in undergrad}
    assert "novelty" in journal_dims
    assert "novelty" not in undergrad_dims
    assert "significance" in undergrad_dims


def test_select_rubrics_filters_by_layer() -> None:
    macro = select_rubrics(RUBRICS_DIR, case_type="journal", layer="macro")
    section = select_rubrics(RUBRICS_DIR, case_type="journal", layer="section")

    macro_dims = {r.dimension for r in macro}
    section_dims = {r.dimension for r in section}
    assert "significance" in macro_dims
    assert "methodology" in section_dims
    assert "significance" not in section_dims


def test_thesis_only_rubrics_are_thesis_only() -> None:
    journal = select_rubrics(RUBRICS_DIR, case_type="journal", layer="macro")
    phd = select_rubrics(RUBRICS_DIR, case_type="thesis_phd", layer="macro")

    journal_dims = {r.dimension for r in journal}
    phd_dims = {r.dimension for r in phd}
    assert "independence" not in journal_dims
    assert "coherence" not in journal_dims
    assert "foundational_mastery" not in journal_dims
    assert {"independence", "coherence", "foundational_mastery"}.issubset(phd_dims)


def test_render_checks_block_lists_check_ids() -> None:
    rubrics = select_rubrics(RUBRICS_DIR, case_type="journal", layer="section")

    block = render_checks_block(rubrics)

    assert "[MET-01]" in block
    assert "[REP-01]" in block
    assert "[EVD-01]" in block


def test_aggregate_issue_graph_basic(tmp_path: Path) -> None:
    deepseek_dir = tmp_path / "deepseek"
    section_dir = deepseek_dir / "sections"
    section_dir.mkdir(parents=True)
    (section_dir / "section_01.json").write_text(
        json.dumps(
            {
                "case_id": "demo",
                "unit_id": "section_01",
                "layer": "section",
                "issues": [
                    {
                        "severity": "major",
                        "dimension": "reproducibility",
                        "type": "method",
                        "triggered_check_ids": ["REP-02"],
                        "anchor": {"page": 25, "line_start": 610, "line_end": 620},
                        "quote": "...",
                        "diagnosis": "Cannot reproduce sampling.",
                        "recommendation": "Specify window and seed.",
                    },
                    {
                        "severity": "moderate",
                        "dimension": "clarity",
                        "type": "writing",
                        "triggered_check_ids": ["CLR-03"],
                        "anchor": {"page": 25, "line_start": 615, "line_end": 615},
                        "quote": "x",
                        "diagnosis": "Unit ambiguous.",
                        "recommendation": "Define unit.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "issue_graph.json"
    graph = aggregate_issue_graph(deepseek_dir, output, case_id="demo")

    assert output.is_file()
    assert len(graph["issues"]) == 2
    assert graph["issues"][0]["id"] == "ISS-0001"
    assert graph["issues"][0]["dimension"] == "reproducibility"
    assert graph["issues"][0]["status"] == "raised"


def test_aggregate_issue_graph_clusters_share_anchor(tmp_path: Path) -> None:
    deepseek_dir = tmp_path / "deepseek"
    (deepseek_dir / "sections").mkdir(parents=True)
    (deepseek_dir / "macro").mkdir(parents=True)
    (deepseek_dir / "sections" / "section_01.json").write_text(
        json.dumps(
            {
                "unit_id": "section_01",
                "layer": "section",
                "issues": [
                    {
                        "severity": "major",
                        "dimension": "methodology",
                        "type": "method",
                        "anchor": {"page": 25, "line_start": 610, "line_end": 620},
                        "quote": "",
                        "diagnosis": "",
                        "recommendation": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (deepseek_dir / "macro" / "whole.json").write_text(
        json.dumps(
            {
                "unit_id": "whole",
                "layer": "macro",
                "issues": [
                    {
                        "severity": "major",
                        "dimension": "methodology",
                        "type": "method",
                        "anchor": {"page": 25, "line_start": 612, "line_end": 615},
                        "quote": "",
                        "diagnosis": "",
                        "recommendation": "",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = aggregate_issue_graph(deepseek_dir, tmp_path / "g.json", case_id="demo")

    clusters = graph["clusters"]
    assert clusters
    assert any(len(c["members"]) >= 2 for c in clusters)


def test_runner_idempotent_and_human_gate(tmp_path: Path) -> None:
    from review_council.cli import main as cli_main

    case_path = create_case("demo_runner", tmp_path, CaseManifest(case_id="demo_runner"))
    (case_path / "normalized" / "manuscript.md").write_text("# A\nclaim\n## B\nbody\n", encoding="utf-8")

    workflow_path = tmp_path / "test_workflow.yaml"
    workflow_path.write_text(
        """name: test_workflow
case_type: journal
stages:
- id: index_markdown
  needs: [normalized/manuscript.md]
  produces: [provenance/source_map.jsonl]
  command: index-markdown
  positional: [normalized/manuscript.md, provenance/source_map.jsonl]
- id: build_units
  needs: [normalized/manuscript.md]
  produces: [units/index.md]
  command: build-units
  positional: [normalized/manuscript.md, units]
- id: dissent
  produces: [reviews/dissent_runner.md]
  gate: human
  instruction: Write reviews/dissent_runner.md.
""",
        encoding="utf-8",
    )

    workflow = load_workflow(workflow_path)
    results = run_workflow(case_path, workflow, cli_main)
    statuses = {r.stage_id: r.status for r in results}
    assert statuses["index_markdown"] == "ok"
    assert statuses["build_units"] == "ok"
    assert statuses["dissent"] == "gate"

    second = run_workflow(case_path, workflow, cli_main)
    second_statuses = {r.stage_id: r.status for r in second}
    assert second_statuses["index_markdown"] == "up_to_date"
    assert second_statuses["build_units"] == "up_to_date"
    assert second_statuses["dissent"] == "gate"


def test_runner_fingerprint_tracks_external_input_and_merge_inputs(tmp_path: Path) -> None:
    case_path = create_case("demo_external_fp", tmp_path, CaseManifest(case_id="demo_external_fp"))
    response = case_path / "reviews" / "secondary_response.txt"
    merge_input = case_path / "reviews" / "secondary.json"

    workflow_path = tmp_path / "external_fp.yaml"
    workflow_path.write_text(
        """name: external_fp
case_type: journal
stages:
- id: external_stage
  produces: [reviews/external_out.txt]
  command: fake-external
  positional: [reviews/external_out.txt]
  flags: ["--external-input=reviews/secondary_response.txt"]
- id: merge_like_stage
  produces: [reviews/merge_out.txt]
  command: fake-merge
  positional: [reviews/merge_out.txt]
  flags: ["--input=reviews/secondary.json"]
""",
        encoding="utf-8",
    )
    workflow = load_workflow(workflow_path)
    calls: list[str] = []

    def fake_cli(argv: list[str]) -> int:
        calls.append(argv[0])
        output = Path(argv[1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"run {len(calls)}\n", encoding="utf-8")
        return 0

    first = run_workflow(case_path, workflow, fake_cli)
    assert [r.status for r in first] == ["ok", "ok"]

    second = run_workflow(case_path, workflow, fake_cli)
    assert [r.status for r in second] == ["up_to_date", "up_to_date"]

    response.parent.mkdir(parents=True, exist_ok=True)
    response.write_text("external model response\n", encoding="utf-8")
    merge_input.write_text('{"source":"manual"}\n', encoding="utf-8")

    third = run_workflow(case_path, workflow, fake_cli)
    assert [r.status for r in third] == ["ok", "ok"]


def test_runner_only_filter_skips_others(tmp_path: Path) -> None:
    from review_council.cli import main as cli_main

    case_path = create_case("demo_only", tmp_path, CaseManifest(case_id="demo_only"))
    (case_path / "normalized" / "manuscript.md").write_text("# A\n", encoding="utf-8")

    workflow_path = tmp_path / "only.yaml"
    workflow_path.write_text(
        """name: t
case_type: journal
stages:
- id: alpha
  produces: [provenance/source_map.jsonl]
  command: index-markdown
  positional: [normalized/manuscript.md, provenance/source_map.jsonl]
- id: beta
  produces: [units/index.md]
  command: build-units
  positional: [normalized/manuscript.md, units]
""",
        encoding="utf-8",
    )
    workflow = load_workflow(workflow_path)
    results = run_workflow(case_path, workflow, cli_main, only={"alpha"})
    statuses = {r.stage_id: r.status for r in results}
    assert statuses["alpha"] == "ok"
    assert statuses["beta"] == "not_selected"


def test_runner_fanout_creates_outputs(tmp_path: Path) -> None:
    from review_council.cli import main as cli_main
    from review_council.segment.units import build_hierarchical_units

    case_path = create_case("demo_fanout", tmp_path, CaseManifest(case_id="demo_fanout"))
    manuscript = case_path / "normalized" / "manuscript.md"
    manuscript.write_text("# Ch1\nA\n# Ch2\nB\n", encoding="utf-8")
    build_hierarchical_units(manuscript, case_path / "units")

    workflow_path = tmp_path / "fanout.yaml"
    workflow_path.write_text(
        """name: fanout_test
case_type: journal
stages:
- id: per_chapter
  fanout_pattern: units/chapters/chapter_*.md
  produces_template: provenance/{stem}.jsonl
  command: index-markdown
  positional_template: ["{unit}", "{output}"]
""",
        encoding="utf-8",
    )
    workflow = load_workflow(workflow_path)
    results = run_workflow(case_path, workflow, cli_main)

    assert results[0].status == "ok"
    assert (case_path / "provenance" / "chapter_01.jsonl").is_file()
    assert (case_path / "provenance" / "chapter_02.jsonl").is_file()


def test_production_workflows_load() -> None:
    workflows_dir = REPO_ROOT / "docs" / "workflows"
    for case_type in ("journal", "thesis_undergrad", "thesis_master", "thesis_phd"):
        path = workflows_dir / f"{case_type}.yaml"
        wf = load_workflow(path)
        assert wf.case_type == case_type
        assert len(wf.stages) >= 8
        for stage in wf.stages:
            assert stage.command or stage.gate, f"{case_type}::{stage.id} has neither command nor gate"


def test_score_text_method_section_high() -> None:
    text = (
        "## Inversion method\n\n"
        "We invert PROSPECT-SAIL using PLSR with RMSE validation. The model "
        "uses training data and reports uncertainty (R^2 = 0.85, RMSE = 0.1).\n"
    )
    score, hits = score_text(text)
    assert score > 5
    assert "method" in hits
    assert "validation" in hits


def test_score_text_introduction_low() -> None:
    text = (
        "## Introduction\n\n"
        "Background and literature review. References to prior work. "
        "Acknowledgments to collaborators.\n"
    )
    score, hits = score_text(text)
    assert score < 5
    assert "low_risk" in hits


def test_build_units_writes_risk_json(tmp_path: Path) -> None:
    from review_council.segment.units import build_hierarchical_units

    manuscript = tmp_path / "manuscript.md"
    units_root = tmp_path / "units"
    manuscript.write_text(
        "# Ch1\n## Methods\nWe invert PROSPECT-SAIL using PLSR with RMSE validation. "
        "Training data was split. Uncertainty is reported.\n"
        "## Background\nLiterature review.\n",
        encoding="utf-8",
    )
    build_hierarchical_units(manuscript, units_root)

    risk_path = units_root / "risk.json"
    assert risk_path.is_file()
    table = load_risk_table(risk_path)
    methods_key = next(k for k in table if k.startswith("sections/"))
    assert table[methods_key] >= 0


def test_runner_fanout_filters_by_risk(tmp_path: Path) -> None:
    from review_council.cli import main as cli_main
    from review_council.segment.units import build_hierarchical_units

    case_path = create_case("demo_risk", tmp_path, CaseManifest(case_id="demo_risk"))
    manuscript = case_path / "normalized" / "manuscript.md"
    manuscript.write_text(
        "# Ch1\n## High-risk\nPROSPECT-SAIL inversion with PLSR. RMSE validation, "
        "training set, test set, uncertainty, R^2, leakage check.\n"
        "## Low-risk\nLiterature review and acknowledgments.\n",
        encoding="utf-8",
    )
    build_hierarchical_units(manuscript, case_path / "units")

    workflow_path = tmp_path / "risk.yaml"
    workflow_path.write_text(
        """name: risk_test
case_type: journal
stages:
- id: filtered_fanout
  fanout_pattern: units/sections/section_*.md
  risk_threshold: 5.0
  risk_table: units/risk.json
  produces_template: provenance/{stem}.jsonl
  command: index-markdown
  positional_template: ["{unit}", "{output}"]
""",
        encoding="utf-8",
    )
    workflow = load_workflow(workflow_path)
    results = run_workflow(case_path, workflow, cli_main)

    assert results[0].status in {"ok", "skipped"}
    assert "risk>=5.0" in results[0].detail


def test_runner_fanout_reports_partial_failure(tmp_path: Path) -> None:
    from review_council.segment.units import build_hierarchical_units

    case_path = create_case("demo_partial", tmp_path, CaseManifest(case_id="demo_partial"))
    manuscript = case_path / "normalized" / "manuscript.md"
    manuscript.write_text("# Ch1\nA\n# Ch2\nB\n", encoding="utf-8")
    build_hierarchical_units(manuscript, case_path / "units")

    workflow_path = tmp_path / "partial.yaml"
    workflow_path.write_text(
        """name: partial_test
case_type: journal
stages:
- id: flaky_fanout
  fanout_pattern: units/chapters/chapter_*.md
  produces_template: provenance/{stem}.jsonl
  command: fake-command
  positional_template: ["{unit}", "{output}"]
""",
        encoding="utf-8",
    )
    workflow = load_workflow(workflow_path)

    def flaky_cli(argv: list[str]) -> int:
        output_path = Path(argv[2])
        if "chapter_02" in argv[1]:
            return 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("ok\n", encoding="utf-8")
        return 0

    results = run_workflow(case_path, workflow, flaky_cli)

    assert results[0].status == "partial"
    assert "chapter_02" in results[0].detail
    assert (case_path / "provenance" / "chapter_01.jsonl").is_file()
    assert not (case_path / "provenance" / "chapter_02.jsonl").exists()


def test_claim_matrix_round_trips(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    claim = Claim(
        id="CLM-0001",
        text="PROSPECT-N inversion improves CCC retrieval RMSE by 25%.",
        type="result",
        source_unit="chapters/chapter_04",
        anchor=ClaimAnchor(page=25, line_start=610, line_end=620),
        evidence_anchors=[
            EvidenceAnchor(type="figure", ref="Fig. 5", strength="moderate", uncertainty_note="single site"),
        ],
    )
    save_claim_matrix(matrix_path, "demo", [claim])

    case_id, claims = load_claim_matrix(matrix_path)
    assert case_id == "demo"
    assert len(claims) == 1
    assert claims[0].id == "CLM-0001"
    assert claims[0].evidence_anchors[0].strength == "moderate"


def test_link_issues_to_claims_by_anchor(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    issue_path = tmp_path / "issue_graph.json"
    save_claim_matrix(
        matrix_path,
        "demo",
        [
            Claim(
                id="CLM-0001",
                text="claim 1",
                source_unit="chapters/chapter_04",
                anchor=ClaimAnchor(page=25, line_start=610, line_end=620),
            ),
            Claim(
                id="CLM-0002",
                text="claim 2",
                source_unit="chapters/chapter_05",
                anchor=ClaimAnchor(page=40, line_start=900, line_end=910),
            ),
        ],
    )
    issue_path.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "issues": [
                    {"id": "ISS-0001", "anchor": {"line_start": 615, "line_end": 615}, "source_units": ["chapter_04"]},
                    {"id": "ISS-0002", "anchor": {"line_start": 905, "line_end": 905}, "source_units": ["chapter_05"]},
                    {"id": "ISS-0003", "anchor": {"line_start": 200, "line_end": 200}, "source_units": ["chapter_01"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = link_issues_to_claims(matrix_path, issue_path, link_window=20)

    assert stats["claims"] == 2
    assert stats["links_added"] == 2
    _, claims = load_claim_matrix(matrix_path)
    by_id = {c.id: c for c in claims}
    assert by_id["CLM-0001"].linked_issues == ["ISS-0001"]
    assert by_id["CLM-0002"].linked_issues == ["ISS-0002"]


def test_link_issues_to_claims_by_similarity_for_whole_claim(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    issue_path = tmp_path / "issue_graph.json"
    save_claim_matrix(
        matrix_path,
        "demo",
        [
            Claim(
                id="CLM-0001",
                text="植被叶绿素反演结果通过独立验证提高精度",
                source_unit="whole",
            )
        ],
    )
    issue_path.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "issues": [
                    {
                        "id": "ISS-0001",
                        "anchor": {},
                        "source_units": ["sections/section_03"],
                        "diagnosis": "叶绿素反演结果缺少独立验证，精度提高证据不足。",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    stats = link_issues_to_claims(matrix_path, issue_path)

    assert stats["links_added"] == 1
    _, claims = load_claim_matrix(matrix_path)
    assert claims[0].linked_issues == ["ISS-0001"]


def test_backfill_claim_anchors_parses_fenced_json_and_normalized_lines(tmp_path: Path) -> None:
    unit = tmp_path / "whole.md"
    unit.write_text(
        "---\nunit_id: whole\nnormalized_line_start: 100\n---\n"
        "The PROSPECT-SAIL inversion improves RMSE validation reliability.\n",
        encoding="utf-8",
    )
    claims = tmp_path / "claims.json"
    claims.write_text(
        """```json
{
  "case_id": "demo",
  "claims": [
    {
      "id": "CLM-0001",
      "text": "PROSPECT-SAIL inversion improves RMSE validation reliability",
      "anchor": {"page": null, "line_start": null, "line_end": null}
    }
  ]
}
```""",
        encoding="utf-8",
    )

    stats = backfill_claim_anchors(claims, unit)
    data = json.loads(claims.read_text(encoding="utf-8"))

    assert stats == {"claims": 1, "backfilled": 1}
    assert data["claims"][0]["anchor"]["line_start"] == 100
    assert data["claims"][0]["anchor"]["line_end"] == 100
    assert data["claims"][0]["anchor_confidence"] in {"medium", "high"}


def test_render_claim_matrix_writes_markdown(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    save_claim_matrix(
        matrix_path,
        "demo",
        [
            Claim(
                id="CLM-0001",
                text="N prior reduces equifinality.",
                type="method",
                source_unit="chapters/chapter_03",
                anchor=ClaimAnchor(page=18, line_start=420, line_end=430),
                evidence_anchors=[EvidenceAnchor(type="argument", ref="Section 3.2", strength="moderate")],
                linked_issues=["ISS-0007"],
            )
        ],
    )
    output = tmp_path / "matrix.md"
    render_claim_matrix_md(matrix_path, output)

    rendered = output.read_text(encoding="utf-8")
    assert "CLM-0001" in rendered
    assert "ISS-0007" in rendered
    assert "moderate" in rendered


def test_synthesize_comments_assigns_default_revision_priority(tmp_path: Path) -> None:
    issue_graph = tmp_path / "issue_graph.json"
    issue_graph.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "id": "ISS-A",
                        "proposed_severity": "major",
                        "type": "method",
                        "dimension": "methodology",
                        "anchor": {"page": 5, "line_start": 10},
                    },
                    {
                        "id": "ISS-B",
                        "proposed_severity": "moderate",
                        "type": "writing",
                        "dimension": "clarity",
                        "anchor": {"page": 6, "line_start": 20},
                    },
                ],
                "clusters": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "draft.json"
    synthesize_comments(issue_graph, output)
    comments = json.loads(output.read_text(encoding="utf-8"))
    by_id = {c["derived_from_issues"][0]: c for c in comments}
    assert by_id["ISS-A"]["revision_priority"] == "high"
    assert by_id["ISS-A"]["final_severity"] == "major"
    assert by_id["ISS-B"]["revision_priority"] == "medium"
    assert by_id["ISS-B"]["final_severity"] == "moderate"


def test_synthesize_comments_severity_filter_and_dedup(tmp_path: Path) -> None:
    issue_graph = tmp_path / "issue_graph.json"
    issue_graph.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "issues": [
                    {"id": "ISS-0001", "proposed_severity": "blocking",
                     "anchor": {"page": 5, "line_start": 10, "line_end": 12},
                     "diagnosis": "B", "recommendation": "fix B", "evidence_quote": "qb"},
                    {"id": "ISS-0002", "proposed_severity": "major",
                     "anchor": {"page": 8, "line_start": 200, "line_end": 200},
                     "diagnosis": "M1", "recommendation": "fix M1", "evidence_quote": "qm1"},
                    {"id": "ISS-0003", "proposed_severity": "moderate",
                     "anchor": {"page": 10, "line_start": 500, "line_end": 500},
                     "diagnosis": "Mo1", "recommendation": "fix Mo1", "evidence_quote": "qmo1"},
                    {"id": "ISS-0004", "proposed_severity": "moderate",
                     "anchor": {"page": 10, "line_start": 510, "line_end": 510},
                     "diagnosis": "Mo2", "recommendation": "fix Mo2", "evidence_quote": "qmo2"},
                    {"id": "ISS-0005", "proposed_severity": "minor",
                     "anchor": {"page": 11, "line_start": 600, "line_end": 600},
                     "diagnosis": "Mi", "recommendation": "fix Mi", "evidence_quote": "qmi"},
                ],
                "clusters": [
                    {"key": "L00500|methodology|method", "members": ["ISS-0003", "ISS-0004"]}
                ],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "review_comments.draft.json"
    stats = synthesize_comments(issue_graph, output)

    comments = json.loads(output.read_text(encoding="utf-8"))
    severities = [c["final_severity"] for c in comments]
    assert severities == ["blocking", "major", "moderate"]
    assert stats["kept_comments"] == 3
    assert stats["input_issues"] == 5
    moderate = next(c for c in comments if c["final_severity"] == "moderate")
    assert sorted(moderate["derived_from_issues"]) == ["ISS-0003", "ISS-0004"]


def test_detail_audit_preserves_low_level_checklist_items(tmp_path: Path) -> None:
    issue_graph = tmp_path / "issue_graph.json"
    issue_graph.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "issues": [
                    {
                        "id": "ISS-0001",
                        "proposed_severity": "major",
                        "type": "method",
                        "dimension": "methodology",
                        "anchor": {"page": 25, "line_start": 610, "line_end": 620},
                        "evidence_quote": "Optimal_N局部窗口根据实际情况设定。",
                        "diagnosis": "N局部窗口大小、采样点数和随机种子未给出，核心策略不可复现。",
                        "recommendation": "补充Optimal_N±多少、采样分布、采样数和随机种子。",
                    },
                    {
                        "id": "ISS-0002",
                        "proposed_severity": "moderate",
                        "type": "format",
                        "dimension": "clarity",
                        "anchor": {"page": 48, "line_start": 1071, "line_end": 1073},
                        "evidence_quote": "CCC-LUT精度为R²=0.692，RMSE=29.46 μg/cm²。",
                        "diagnosis": "CCC单位疑似与Cab单位混用。",
                        "recommendation": "统一CCC单位并说明换算关系。",
                    },
                    {
                        "id": "ISS-0003",
                        "proposed_severity": "minor",
                        "type": "writing",
                        "dimension": "clarity",
                        "anchor": {"page": 25, "line_start": 700, "line_end": 700},
                        "diagnosis": "一句普通表达可以更顺。",
                        "recommendation": "润色句子。",
                    },
                ],
                "clusters": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "detail_audit.json"

    stats = build_detail_audit(issue_graph, output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert stats["detail_items"] == 2
    categories = {item["category"] for item in data["items"]}
    assert "method_parameter" in categories
    assert "unit_consistency" in categories
    assert any("随机种子" in item["text"] for item in data["items"])


def test_compose_author_review_merges_strategy_and_detail_pool(tmp_path: Path) -> None:
    paper_shape = tmp_path / "paper_shape.md"
    paper_shape.write_text(
        "# Paper Shape\n\n"
        "## Top 3 Transformation Actions\n\n"
        "1. **重组第四章。** 以N先验与随机N的配对控制比较为主线。\n"
        "2. **压缩第五章。** 水盐光谱响应只保留为背景或附录。\n"
        "3. **重写创新点。** 解释N对Cab和CCC提升幅度不同的原因。\n",
        encoding="utf-8",
    )
    strategic = tmp_path / "strategic.json"
    strategic.write_text(
        json.dumps(
            [
                {
                    "id": "CMT-0001",
                    "track": "main_argument",
                    "final_severity": "major",
                    "revision_priority": "high",
                    "page": None,
                    "line_start": 100,
                    "line_end": 110,
                    "quote": "6.2 主要创新点",
                    "comment": "paper_shape Transformation Action 3 requires explaining what N teaches about Cab and CCC.",
                    "recommendation": "Rewrite the innovation section as one integrated finding.",
                },
                {
                    "id": "CMT-0002",
                    "track": "references_format",
                    "final_severity": "minor",
                    "revision_priority": "low",
                    "page": None,
                    "line_start": 200,
                    "comment": "Reference formatting issue.",
                    "recommendation": "Fix references.",
                },
            ]
        ),
        encoding="utf-8",
    )
    detail = tmp_path / "detail.json"
    detail.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "items": [
                    {
                        "type": "checklist_item",
                        "category": "method_parameter",
                        "priority": "high",
                        "anchor": {"page": None, "line_start": 610, "line_end": 620},
                        "text": "N局部窗口大小、采样点数和随机种子未给出。",
                        "recommendation": "补充Optimal_N±多少、采样分布、采样数和随机种子。",
                    },
                    {
                        "type": "checklist_item",
                        "category": "unit_consistency",
                        "priority": "medium",
                        "anchor": {"page": None, "line_start": 1071, "line_end": 1073},
                        "text": "CCC单位疑似与Cab单位混用。",
                        "recommendation": "统一CCC单位。",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_map = tmp_path / "source_map.jsonl"
    source_map.write_text(
        "\n".join(
            [
                '{"anchor_id":"L00100","normalized_line_start":100,"source_page":5}',
                '{"anchor_id":"L00610","normalized_line_start":610,"source_page":25}',
                '{"anchor_id":"L01071","normalized_line_start":1071,"source_page":48}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_md = tmp_path / "author.md"
    output_json = tmp_path / "package.json"

    stats = compose_author_review(
        paper_shape_path=paper_shape,
        strategic_comments_path=strategic,
        detail_audit_path=detail,
        source_map_path=source_map,
        output_md_path=output_md,
        output_json_path=output_json,
    )
    text = output_md.read_text(encoding="utf-8")

    assert stats["revision_goals"] == 3
    assert "## 总体修改方向" in text
    assert "## 一、主线与结构" in text
    assert "## 四、必须补齐的技术细节" in text
    assert "## 五、格式、单位与文字问题" in text
    assert "N局部窗口大小" in text
    assert "CCC单位" in text
    assert "CMT-0001" not in text
    assert "paper_shape" not in text
    assert output_json.is_file()


def test_author_polish_cleans_process_language(tmp_path: Path) -> None:
    input_md = tmp_path / "in.md"
    output_md = tmp_path / "out.md"
    input_md.write_text(
        "This follows paper_shape Transformation Action 2 and ISS-0001 from DeepSeek meta-review.\n",
        encoding="utf-8",
    )

    polish_author_review(input_md, output_md)
    text = output_md.read_text(encoding="utf-8")

    assert "ISS-0001" not in text
    assert "paper_shape" not in text
    assert "DeepSeek" not in text
    assert "meta-review" not in text


def test_severity_caps_demote_citation_and_format() -> None:
    citation_major = {"proposed_severity": "major", "type": "citation", "dimension": "integrity"}
    format_major = {"proposed_severity": "major", "type": "format", "dimension": "clarity"}
    method_major = {"proposed_severity": "major", "type": "method", "dimension": "methodology"}

    assert _apply_severity_caps(citation_major) == "minor"
    assert _apply_severity_caps(format_major) == "minor"
    assert _apply_severity_caps(method_major) == "major"


def test_split_meta_review_response_parses_two_sections() -> None:
    text = """## Meta-Review Narrative

Summary paragraph.

```json
[{"id": "CMT-0001", "track": "main_argument", "severity": "major"}]
```
"""
    narrative, comments_json = split_meta_review_response(text)
    assert narrative.startswith("## Meta-Review Narrative")
    assert "Summary paragraph." in narrative
    parsed = json.loads(comments_json)
    assert parsed[0]["id"] == "CMT-0001"
    assert parsed[0]["track"] == "main_argument"


def test_render_comments_groups_by_track(tmp_path: Path) -> None:
    manuscript = tmp_path / "manuscript.md"
    source_map = tmp_path / "source_map.jsonl"
    comments = tmp_path / "comments.json"
    output = tmp_path / "out.md"

    manuscript.write_text("# T\n\nbody\n", encoding="utf-8")
    build_markdown_line_map(manuscript, source_map)
    comments.write_text(
        json.dumps(
            [
                {
                    "id": "CMT-001",
                    "track": "methods",
                    "severity": "major",
                    "comment": "Method issue text.",
                    "anchor_id": "L00003",
                },
                {
                    "id": "CMT-002",
                    "track": "main_argument",
                    "severity": "blocking",
                    "comment": "Main argument issue text.",
                    "anchor_id": "L00003",
                },
            ]
        ),
        encoding="utf-8",
    )

    from review_council.comments import render_comments as render

    render(comments, source_map, output)
    rendered = output.read_text(encoding="utf-8")

    main_pos = rendered.find("## Main Argument")
    methods_pos = rendered.find("## Methods")
    assert 0 <= main_pos < methods_pos


def test_render_modes_author_hides_supervisor_keeps_provenance(tmp_path: Path) -> None:
    source_map = tmp_path / "source_map.jsonl"
    source_map.write_text("", encoding="utf-8")
    comments = tmp_path / "comments.json"
    comments.write_text(
        json.dumps(
            [
                {
                    "id": "C-1",
                    "comment": "x",
                    "line_start": 10,
                    "final_severity": "major",
                    "revision_priority": "high",
                    "derived_from_issues": ["ISS-0007"],
                    "linked_claims": ["CLM-0003"],
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out.md"
    from review_council.comments import render_comments as render

    render(comments, source_map, output, mode="author")
    rendered_author = output.read_text(encoding="utf-8")
    assert "Provenance" not in rendered_author
    assert "ISS-0007" not in rendered_author
    assert "Author-Facing Review Comments" in rendered_author
    assert "Priority High" in rendered_author

    render(comments, source_map, output, mode="supervisor")
    rendered_supervisor = output.read_text(encoding="utf-8")
    assert "Provenance" in rendered_supervisor
    assert "ISS-0007" in rendered_supervisor
    assert "Supervisor Internal Review" in rendered_supervisor
    assert "priority=high" in rendered_supervisor


def test_render_comments_zh_locale_and_hide_priority(tmp_path: Path) -> None:
    source_map = tmp_path / "source_map.jsonl"
    source_map.write_text("", encoding="utf-8")
    comments = tmp_path / "comments.json"
    comments.write_text(
        json.dumps(
            [
                {
                    "id": "C-1",
                    "track": "methods",
                    "comment": "方法部分需要补充验证细节。",
                    "line_start": 10,
                    "final_severity": "major",
                    "revision_priority": "high",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out.md"

    from review_council.comments import render_comments as render

    render(comments, source_map, output, locale="zh")
    rendered = output.read_text(encoding="utf-8")
    assert "## 方法" in rendered
    assert "优先级：高" in rendered

    render(comments, source_map, output, locale="zh", hide_priority=True)
    hidden = output.read_text(encoding="utf-8")
    assert "优先级" not in hidden
    assert "### 1. Major" in hidden


def test_render_author_comments_redacts_inline_provenance_tokens(tmp_path: Path) -> None:
    source_map = tmp_path / "source_map.jsonl"
    source_map.write_text("", encoding="utf-8")
    comments = tmp_path / "comments.json"
    comments.write_text(
        json.dumps(
            [
                {
                    "id": "C-1",
                    "comment": "Fix this issue (ISS-0002) and related claim CLM-0007. This serves paper_shape Transformation Action 2 and CMT-0005.",
                    "recommendation": "Use ISS-0002 only internally. The cheap reviewers raised multiple issues.",
                    "line_start": 10,
                    "final_severity": "major",
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out.md"

    from review_council.comments import render_comments as render

    render(comments, source_map, output, mode="author")
    rendered_author = output.read_text(encoding="utf-8")
    assert "ISS-0002" not in rendered_author
    assert "CLM-0007" not in rendered_author
    assert "CMT-0005" not in rendered_author
    assert "paper_shape" not in rendered_author
    assert "Transformation Action" not in rendered_author
    assert "cheap reviewers" not in rendered_author

    render(comments, source_map, output, mode="supervisor")
    rendered_supervisor = output.read_text(encoding="utf-8")
    assert "ISS-0002" in rendered_supervisor
    assert "CLM-0007" in rendered_supervisor


def test_backfill_prefers_section_over_chapter_over_macro(tmp_path: Path) -> None:
    units_root = tmp_path / "units"
    (units_root / "macro").mkdir(parents=True)
    (units_root / "chapters").mkdir(parents=True)
    (units_root / "sections").mkdir(parents=True)
    (units_root / "macro" / "whole.md").write_text(
        "---\nnormalized_line_start: 1\n---\nx\n", encoding="utf-8"
    )
    (units_root / "chapters" / "chapter_05.md").write_text(
        "---\nnormalized_line_start: 800\n---\nx\n", encoding="utf-8"
    )
    (units_root / "sections" / "section_15.md").write_text(
        "---\nnormalized_line_start: 855\n---\nx\n", encoding="utf-8"
    )

    issues = [
        {"id": "ISS-A", "anchor": {}, "source_units": ["macro/whole", "chapters/chapter_05", "sections/section_15"]},
    ]
    comments = [{"id": "C", "page": None, "line_start": None, "derived_from_issues": ["ISS-A"]}]

    backfill_anchors(comments, issues, units_root=units_root)

    assert comments[0]["line_start"] == 855


def test_backfill_anchors_uses_issue_anchor_then_unit_start(tmp_path: Path) -> None:
    units_root = tmp_path / "units"
    (units_root / "chapters").mkdir(parents=True)
    (units_root / "chapters" / "chapter_02.md").write_text(
        "---\nunit_id: chapter_02\ntitle: Materials\nnormalized_line_start: 320\nnormalized_line_end: 480\n---\nbody\n",
        encoding="utf-8",
    )
    issues = [
        {
            "id": "ISS-A",
            "anchor": {"page": 12, "line_start": 350, "line_end": 360},
            "source_units": ["chapters/chapter_02"],
        },
        {
            "id": "ISS-B",
            "anchor": {"page": None, "line_start": None, "line_end": None},
            "source_units": ["chapters/chapter_02"],
        },
    ]
    comments = [
        {"id": "CMT-1", "page": None, "line_start": None, "derived_from_issues": ["ISS-A"]},
        {"id": "CMT-2", "page": None, "line_start": None, "derived_from_issues": ["ISS-B"]},
    ]

    backfilled = backfill_anchors(comments, issues, units_root=units_root)

    assert backfilled == 2
    assert comments[0]["page"] == 12
    assert comments[0]["line_start"] == 350
    assert comments[1]["line_start"] == 320
    assert comments[1]["page"] is None


def test_render_comments_resolves_page_from_line(tmp_path: Path) -> None:
    source_map = tmp_path / "source_map.jsonl"
    source_map.write_text(
        "\n".join(
            [
                '{"anchor_id": "L00100", "normalized_path": "x.md", "normalized_line_start": 100, "normalized_line_end": 100, "source_path": "x.pdf", "source_page": 5, "source_line_start": null, "source_line_end": null, "text": ""}',
                '{"anchor_id": "L00200", "normalized_path": "x.md", "normalized_line_start": 200, "normalized_line_end": 200, "source_path": "x.pdf", "source_page": 9, "source_line_start": null, "source_line_end": null, "text": ""}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    comments = tmp_path / "comments.json"
    comments.write_text(
        json.dumps([{"id": "C-1", "comment": "x", "line_start": 150, "line_end": 150}]),
        encoding="utf-8",
    )
    output = tmp_path / "out.md"

    from review_council.comments import render_comments as render

    render(comments, source_map, output)
    rendered = output.read_text(encoding="utf-8")
    assert "p. 5" in rendered


def test_dimensions_taxonomy_is_stable() -> None:
    expected = {
        "significance",
        "novelty",
        "methodology",
        "evidence",
        "reproducibility",
        "clarity",
        "independence",
        "coherence",
        "foundational_mastery",
        "integrity",
    }
    assert set(DIMENSIONS) == expected


def test_deepseek_retries_retryable_errors_then_succeeds() -> None:
    import ssl
    import urllib.error

    calls: list[int] = []
    sleeps: list[float] = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")

    def opener(_request, timeout: int) -> FakeResponse:
        calls.append(timeout)
        if len(calls) == 1:
            raise urllib.error.URLError(ssl.SSLEOFError("EOF occurred"))
        return FakeResponse()

    response = chat_completion(
        DeepSeekRequest(api_key="test", prompt="hello"),
        opener=opener,
        sleep=sleeps.append,
    )

    assert response == "ok"
    assert len(calls) == 2
    assert sleeps == [1.5]


def test_deepseek_does_not_retry_auth_errors() -> None:
    import io
    import urllib.error

    sleeps: list[float] = []

    def opener(_request, timeout: int):
        raise urllib.error.HTTPError(
            url="https://api.deepseek.com/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error":"bad key"}'),
        )

    with pytest.raises(RuntimeError, match="HTTP 401"):
        chat_completion(
            DeepSeekRequest(api_key="bad", prompt="hello"),
            opener=opener,
            sleep=sleeps.append,
        )

    assert sleeps == []


# --- author editorial layer ------------------------------------------------


from review_council.author_editorial import (
    DEFAULT_VOICE,
    VOICE_PROFILES,
    build_author_review_plan,
    find_internal_tokens,
    redact_internal_tokens,
    run_author_editorial_rewrite,
)


def _write_paper_shape(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Paper Shape\n"
        "\n"
        "## Best version\n"
        "The strongest form of this paper centers a single methodological claim and "
        "validates it on independent data.\n"
        "\n"
        "## Top 3 Transformation Actions\n"
        "1. Reframe the abstract around the central methodological contribution.\n"
        "2. Tighten the validation chapter to address generalization explicitly.\n"
        "3. Compress the redundant background sections into one.\n",
        encoding="utf-8",
    )


def _write_meta_comments(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "id": "CMT-0001",
                    "track": "main_argument",
                    "comment": "The main argument is buried under background.",
                    "recommendation": "Lead with the contribution.",
                    "final_severity": "blocking",
                    "revision_priority": "high",
                    "derived_from_issues": ["ISS-0007"],
                },
                {
                    "id": "CMT-0002",
                    "track": "methods",
                    "comment": "Method parameters are not fully reported.",
                    "recommendation": "Add the search range and seed.",
                    "final_severity": "major",
                    "revision_priority": "high",
                    "derived_from_issues": ["ISS-0011"],
                },
                {
                    "id": "CMT-0003",
                    "track": "references_format",
                    "comment": "A few citations use mismatched styles.",
                    "recommendation": "Normalize references.",
                    "final_severity": "minor",
                    "revision_priority": "low",
                },
            ]
        ),
        encoding="utf-8",
    )


def _write_detail_audit(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "items": [
                    {
                        "category": "method_parameter",
                        "category_label": "方法参数与可复现性",
                        "priority": "high",
                        "anchor": {"page": 12, "line_start": 320},
                        "text": "搜索窗口和随机种子未给出。",
                        "recommendation": "补 N 范围与 seed。",
                    },
                    {
                        "category": "unit_consistency",
                        "category_label": "单位一致性",
                        "priority": "medium",
                        "anchor": {"page": 18, "line_start": 410},
                        "text": "Cab 单位前后不一致。",
                        "recommendation": "统一为 μg/cm²。",
                    },
                ],
                "counts_by_category": {"method_parameter": 1, "unit_consistency": 1},
            }
        ),
        encoding="utf-8",
    )


def _write_source_map(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_find_and_redact_internal_tokens_round_trip() -> None:
    leaky = (
        "Per Transformation Action 1, ISS-0007 and CMT-0002 raised by DeepSeek meta-review "
        "(see issue graph and rubric MET-01) flag a major problem. The paper_shape says the "
        "best version is X. blocking severity."
    )
    leaks = find_internal_tokens(leaky)
    assert any(token.startswith("ISS-") for token in leaks)
    assert any("DeepSeek" in token for token in leaks)
    assert any("Transformation Action" in token for token in leaks)

    cleaned = redact_internal_tokens(leaky)
    assert "DeepSeek" not in cleaned
    assert "ISS-" not in cleaned and "CMT-" not in cleaned and "MET-" not in cleaned
    assert "paper_shape" not in cleaned and "paper shape" not in cleaned.lower()
    assert "Transformation Action" not in cleaned
    assert "issue graph" not in cleaned.lower()
    assert "rubric" not in cleaned.lower()
    # English severity tokens replaced; "major" word boundary should be gone.
    assert " major " not in cleaned and " blocking " not in cleaned
    # After cleaning the validator should be silent.
    assert find_internal_tokens(cleaned) == []


def test_voice_profiles_have_reviewer_and_senior_peer() -> None:
    assert "reviewer" in VOICE_PROFILES
    assert "senior_peer" in VOICE_PROFILES
    assert DEFAULT_VOICE in VOICE_PROFILES


def test_build_author_review_plan_offline_separates_keep_and_demote(tmp_path: Path) -> None:
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"
    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)

    stats = build_author_review_plan(
        paper_shape_path=paper_shape,
        meta_comments_path=meta,
        detail_audit_path=detail,
        output_json_path=plan_json,
        output_md_path=plan_md,
        voice="senior_peer",
        api_key=None,
    )
    assert stats["source"] == "offline"
    assert stats["voice"] == "senior_peer"

    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    assert len(plan["revision_directions"]) == 3
    assert plan["voice"] == "senior_peer"
    must_keep_ids = {r["id"] for r in plan["must_keep_strategic"]}
    demoted_ids = {r["id"] for r in plan["demote_or_drop"]}
    assert "CMT-0001" in must_keep_ids and "CMT-0002" in must_keep_ids
    assert "CMT-0003" in demoted_ids
    # Plan markdown is internal — not redacted, but must contain the directions header.
    md = plan_md.read_text(encoding="utf-8")
    assert "三条总体修改方向" in md


def test_run_author_editorial_rewrite_offline_redacts_and_uses_voice(tmp_path: Path) -> None:
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    source_map = tmp_path / "provenance" / "source_map.jsonl"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"
    output = tmp_path / "comments" / "author_facing_comments.md"
    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)
    _write_source_map(source_map)

    build_author_review_plan(
        paper_shape_path=paper_shape,
        meta_comments_path=meta,
        detail_audit_path=detail,
        output_json_path=plan_json,
        output_md_path=plan_md,
        voice="senior_peer",
        api_key=None,
    )

    stats = run_author_editorial_rewrite(
        paper_shape_path=paper_shape,
        plan_path=plan_json,
        meta_comments_path=meta,
        detail_audit_path=detail,
        source_map_path=source_map,
        output_md_path=output,
        voice="senior_peer",
        api_key=None,
    )
    assert stats["used_strong"] is False
    assert stats["leaks"] == []

    text = output.read_text(encoding="utf-8")
    # Senior-peer opening must appear.
    assert "博士生" in text
    # Three overall revision directions must lead the body.
    assert "总体修改方向" in text
    # Strong-no-leak guarantee.
    assert "DeepSeek" not in text
    assert "ISS-" not in text and "CMT-" not in text and "MET-" not in text
    assert "Transformation Action" not in text
    assert "paper_shape" not in text
    # Detail pool surfaces.
    assert "方法参数" in text or "搜索窗口" in text


def test_run_author_editorial_rewrite_voice_reviewer_changes_opening(tmp_path: Path) -> None:
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    source_map = tmp_path / "provenance" / "source_map.jsonl"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"
    output = tmp_path / "comments" / "author_facing_comments.md"
    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)
    _write_source_map(source_map)

    build_author_review_plan(
        paper_shape_path=paper_shape, meta_comments_path=meta,
        detail_audit_path=detail, output_json_path=plan_json,
        output_md_path=plan_md, voice="reviewer", api_key=None,
    )
    run_author_editorial_rewrite(
        paper_shape_path=paper_shape, plan_path=plan_json,
        meta_comments_path=meta, detail_audit_path=detail,
        source_map_path=source_map, output_md_path=output,
        voice="reviewer", api_key=None,
    )
    text = output.read_text(encoding="utf-8")
    assert "审稿意见" in text
    # senior_peer opener should NOT be present in reviewer voice.
    assert "博士生" not in text


def test_thesis_undergrad_workflow_includes_editorial_stages() -> None:
    workflows_dir = REPO_ROOT / "docs" / "workflows"
    wf = load_workflow(workflows_dir / "thesis_undergrad.yaml")
    ids = [stage.id for stage in wf.stages]
    assert "author_review_plan" in ids
    assert "author_editorial_rewrite" in ids
    # rewrite stage must come after the plan stage.
    assert ids.index("author_editorial_rewrite") > ids.index("author_review_plan")


# --- methodology adversary -------------------------------------------------


from review_council.methodology_adversary import (
    fatal_and_major_findings,
    run_methodology_adversary,
)


def test_methodology_adversary_offline_stub_when_no_api_key(tmp_path: Path) -> None:
    intro = tmp_path / "ch1.md"
    methods = tmp_path / "ch3.md"
    results = tmp_path / "ch4.md"
    intro.write_text("# intro\nresearch goal X\n", encoding="utf-8")
    methods.write_text("# methods\nstep A\n", encoding="utf-8")
    results.write_text("# results\nfinding A\n", encoding="utf-8")
    output = tmp_path / "reviews" / "methodology_adversary.json"
    template = tmp_path / "tpl.md"
    template.write_text("prompt template body\n", encoding="utf-8")

    stats = run_methodology_adversary(
        intro_path=intro,
        methods_path=methods,
        results_path=results,
        output_path=output,
        prompt_template=template,
        api_key=None,
        case_id="demo",
    )
    assert stats["source"] == "offline_stub"
    assert stats["fatal"] == 0 and stats["major"] == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"] == "offline_stub"
    assert payload["hidden_assumptions"] == []
    assert "Manual methodology review required" in payload["note"]


def test_fatal_and_major_findings_filters_correctly(tmp_path: Path) -> None:
    adversary = tmp_path / "methodology_adversary.json"
    adversary.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "source": "strong_model",
                "hidden_assumptions": [
                    {"id": "MA-01", "assumption": "fatal one", "breakage": "core breaks", "reported_check": "none", "severity": "fatal"},
                    {"id": "MA-02", "assumption": "major one", "breakage": "branch breaks", "reported_check": "none", "severity": "major"},
                    {"id": "MA-03", "assumption": "moderate one", "breakage": "minor breaks", "reported_check": "yes", "severity": "moderate"},
                ],
                "unmet_research_goals": [
                    {"stated_goal": "decouple X and Y", "evidence_in_paper": "none", "verdict": "not_delivered"},
                    {"stated_goal": "describe Z", "evidence_in_paper": "Section 2", "verdict": "delivered"},
                ],
            }
        ),
        encoding="utf-8",
    )
    findings = fatal_and_major_findings(adversary)
    ids = [f["id"] for f in findings]
    severities = [f["severity"] for f in findings]
    assert "MA-01" in ids and "MA-02" in ids
    assert "MA-03" not in ids
    # The not-delivered goal should be appended as an additional finding.
    assert any("研究目标未在论文中兑现" in f["assumption"] for f in findings)
    # The delivered goal should NOT show up.
    assert not any("describe Z" in f.get("assumption", "") for f in findings)
    # All retained findings should be fatal or major.
    assert set(severities) <= {"fatal", "major"}


def test_plan_offline_force_merges_adversary_into_must_keep(tmp_path: Path) -> None:
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    adversary = tmp_path / "reviews" / "methodology_adversary.json"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"

    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)
    adversary.parent.mkdir(parents=True, exist_ok=True)
    adversary.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "source": "strong_model",
                "hidden_assumptions": [
                    {
                        "id": "MA-01",
                        "assumption": "Joint-inversion identifiability not demonstrated",
                        "breakage": "If violated, all downstream conclusions about Optimal_N collapse",
                        "reported_check": "none",
                        "severity": "fatal",
                    },
                    {
                        "id": "MA-02",
                        "assumption": "Soft assumption",
                        "breakage": "Minor branch fails",
                        "reported_check": "partial",
                        "severity": "moderate",
                    },
                ],
                "unmet_research_goals": [],
            }
        ),
        encoding="utf-8",
    )

    from review_council.author_editorial import build_author_review_plan

    stats = build_author_review_plan(
        paper_shape_path=paper_shape,
        meta_comments_path=meta,
        detail_audit_path=detail,
        output_json_path=plan_json,
        output_md_path=plan_md,
        voice="senior_peer",
        api_key=None,
        methodology_adversary_path=adversary,
    )
    assert stats["source"] == "offline"

    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    must_keep = plan["must_keep_strategic"]
    fatal = next((r for r in must_keep if r.get("id") == "MA-01"), None)
    moderate = next((r for r in must_keep if r.get("id") == "MA-02"), None)
    assert fatal is not None
    assert fatal["track"] == "methodology_adversary"
    assert fatal["severity"] == "blocking"
    assert fatal["from_adversary"] is True
    # Moderate ones are not force-merged.
    assert moderate is None


def test_offline_rewrite_surfaces_adversary_into_methods_section(tmp_path: Path) -> None:
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    adversary = tmp_path / "reviews" / "methodology_adversary.json"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"
    source_map = tmp_path / "provenance" / "source_map.jsonl"
    output = tmp_path / "comments" / "author_facing_comments.md"

    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)
    _write_source_map(source_map)
    adversary.parent.mkdir(parents=True, exist_ok=True)
    adversary.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "source": "strong_model",
                "hidden_assumptions": [
                    {
                        "id": "MA-01",
                        "assumption": "PROSPECT 二参数联合反演可识别性未论证",
                        "breakage": "下游所有用 Optimal_N 的结论都建立在反演解唯一上",
                        "reported_check": "none",
                        "severity": "fatal",
                    }
                ],
                "unmet_research_goals": [],
            }
        ),
        encoding="utf-8",
    )

    from review_council.author_editorial import (
        build_author_review_plan,
        run_author_editorial_rewrite,
    )

    build_author_review_plan(
        paper_shape_path=paper_shape,
        meta_comments_path=meta,
        detail_audit_path=detail,
        output_json_path=plan_json,
        output_md_path=plan_md,
        voice="senior_peer",
        api_key=None,
        methodology_adversary_path=adversary,
    )

    stats = run_author_editorial_rewrite(
        paper_shape_path=paper_shape,
        plan_path=plan_json,
        meta_comments_path=meta,
        detail_audit_path=detail,
        source_map_path=source_map,
        output_md_path=output,
        voice="senior_peer",
        api_key=None,
    )
    assert stats["leaks"] == []
    text = output.read_text(encoding="utf-8")
    # The adversary fatal assumption must surface in the methods section.
    assert "可识别性" in text or "联合反演" in text
    assert "二、方法与可复现性" in text
    # No internal-token leakage.
    assert "MA-01" not in text


def test_thesis_undergrad_workflow_includes_methodology_adversary() -> None:
    workflows_dir = REPO_ROOT / "docs" / "workflows"
    wf = load_workflow(workflows_dir / "thesis_undergrad.yaml")
    ids = [stage.id for stage in wf.stages]
    assert "methodology_adversary" in ids
    assert ids.index("methodology_adversary") < ids.index("author_review_plan")


# --- provider registry ----------------------------------------------------


from review_council.providers import (
    CompletionRequest,
    complete as provider_complete,
    is_registered,
    list_providers,
)
from review_council.providers.manual_provider import ManualPendingError


def test_provider_registry_lists_all_built_ins() -> None:
    names = set(list_providers())
    assert {"deepseek", "manual", "external_file", "openai", "gpt", "claude"} <= names
    assert is_registered("manual")
    assert is_registered("deepseek")


def test_provider_complete_unknown_raises_actionable_error() -> None:
    with pytest.raises(ValueError, match="unknown provider"):
        provider_complete(CompletionRequest(prompt="x"), provider="not_a_provider")


def test_openai_provider_stub_points_to_manual() -> None:
    with pytest.raises(NotImplementedError, match="manual"):
        provider_complete(CompletionRequest(prompt="x"), provider="openai")


def test_claude_provider_stub_points_to_manual() -> None:
    with pytest.raises(NotImplementedError, match="manual"):
        provider_complete(CompletionRequest(prompt="x"), provider="claude")


def test_manual_provider_reads_external_file(tmp_path: Path) -> None:
    response_path = tmp_path / "response.json"
    response_path.write_text('{"hello": "world"}', encoding="utf-8")
    out = provider_complete(
        CompletionRequest(prompt="ignored", external_input_path=response_path),
        provider="manual",
    )
    assert out == '{"hello": "world"}'


def test_manual_provider_caches_prompt_and_raises_when_response_missing(tmp_path: Path) -> None:
    response_path = tmp_path / "response.txt"  # not created
    cache_path = tmp_path / "prompt.md"
    with pytest.raises(ManualPendingError) as exc_info:
        provider_complete(
            CompletionRequest(
                prompt="render me",
                external_input_path=response_path,
                prompt_cache_path=cache_path,
            ),
            provider="manual",
        )
    assert cache_path.exists()
    assert cache_path.read_text(encoding="utf-8") == "render me"
    assert exc_info.value.response_path == response_path


# --- methodology_adversary multi-run + manual mode -----------------------


def test_methodology_adversary_manual_pending_with_skip(tmp_path: Path) -> None:
    intro = tmp_path / "ch1.md"
    methods = tmp_path / "ch3.md"
    results = tmp_path / "ch4.md"
    template = tmp_path / "tpl.md"
    response = tmp_path / "secondary_response.json"
    cache = tmp_path / "secondary_prompt.md"
    output = tmp_path / "reviews" / "methodology_adversary.secondary.json"
    intro.write_text("intro", encoding="utf-8")
    methods.write_text("methods", encoding="utf-8")
    results.write_text("results", encoding="utf-8")
    template.write_text("prompt body", encoding="utf-8")

    stats = run_methodology_adversary(
        intro_path=intro,
        methods_path=methods,
        results_path=results,
        output_path=output,
        prompt_template=template,
        api_key=None,
        case_id="demo",
        provider="manual",
        external_input=response,
        prompt_cache=cache,
        skip_if_missing=True,
    )
    assert stats["source"] == "manual_pending"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"] == "manual_pending"
    assert payload["expected_response_path"].endswith("secondary_response.json")
    assert cache.exists()
    assert cache.read_text(encoding="utf-8").startswith("prompt body")


def test_methodology_adversary_manual_with_response_writes_runs(tmp_path: Path) -> None:
    intro = tmp_path / "ch1.md"
    methods = tmp_path / "ch3.md"
    results = tmp_path / "ch4.md"
    template = tmp_path / "tpl.md"
    response = tmp_path / "response.json"
    output = tmp_path / "reviews" / "methodology_adversary.secondary.json"
    intro.write_text("intro", encoding="utf-8")
    methods.write_text("methods", encoding="utf-8")
    results.write_text("results", encoding="utf-8")
    template.write_text("prompt", encoding="utf-8")
    response.write_text(
        json.dumps(
            {
                "hidden_assumptions": [
                    {"id": "X-01", "assumption": "secondary fatal A", "breakage": "main result", "reported_check": "none", "severity": "fatal"}
                ],
                "unmet_research_goals": [],
                "headline_claim_dependencies": [
                    {"id": "X-HCD-01", "paper_claim": "headline X", "depends_on_assumptions": ["X-01"], "if_violated_downgrade_to": "soft X", "severity": "fatal"}
                ],
            }
        ),
        encoding="utf-8",
    )

    stats = run_methodology_adversary(
        intro_path=intro,
        methods_path=methods,
        results_path=results,
        output_path=output,
        prompt_template=template,
        api_key=None,
        case_id="demo",
        provider="manual",
        external_input=response,
    )
    assert stats["source"] == "strong_model"
    payload = json.loads(output.read_text(encoding="utf-8"))
    # Top-level lists keep backwards compat with fatal_and_major_findings.
    assert payload["hidden_assumptions"][0]["severity"] == "fatal"
    # New shape: per-run breakdown also recorded.
    assert payload["runs"][0]["run_index"] == 1


# --- adversary merge ------------------------------------------------------


def _write_adversary(path: Path, *, provider: str, hidden: list[dict], deps: list[dict] | None = None, goals: list[dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "provider": provider,
                "model": f"{provider}-test",
                "source": "strong_model",
                "n_runs": 1,
                "hidden_assumptions": hidden,
                "unmet_research_goals": goals or [],
                "headline_claim_dependencies": deps or [],
                "runs": [
                    {
                        "run_index": 1,
                        "temperature": 0.2,
                        "hidden_assumptions": hidden,
                        "unmet_research_goals": goals or [],
                        "headline_claim_dependencies": deps or [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_merge_adversaries_classifies_agreement(tmp_path: Path) -> None:
    from review_council.adversary_merge import merge_adversaries

    primary = tmp_path / "primary.json"
    secondary = tmp_path / "secondary.json"
    _write_adversary(
        primary,
        provider="deepseek",
        hidden=[
            {"id": "MA-01", "assumption": "joint inversion identifiability not shown", "breakage": "core fails", "reported_check": "none", "severity": "fatal"},
            {"id": "MA-02", "assumption": "comparison fairness assumed across LUT sizes", "breakage": "B fails", "reported_check": "none", "severity": "major"},
            {"id": "MA-03", "assumption": "deepseek-only finding about preprocessing", "breakage": "minor branch", "reported_check": "none", "severity": "fatal"},
        ],
    )
    _write_adversary(
        secondary,
        provider="claude",
        hidden=[
            {"id": "HA-1", "assumption": "joint inversion identifiability not demonstrated", "breakage": "core fails", "reported_check": "none", "severity": "major"},
            {"id": "HA-2", "assumption": "claude-only finding about cross-canopy uniformity", "breakage": "branch", "reported_check": "none", "severity": "major"},
        ],
    )

    merged_out = tmp_path / "merged.json"
    md_out = tmp_path / "merged.md"
    merged = merge_adversaries([primary, secondary], merged_out, md_output_path=md_out)

    assert sorted(merged["providers"]) == ["claude", "deepseek"]
    assert merged["n_total_runs"] == 2

    by_assumption = {ha["assumption"][:30]: ha for ha in merged["hidden_assumptions"]}
    # Joint identifiability appears in both providers but with different severities -> conflict.
    joint = next(ha for ha in merged["hidden_assumptions"] if "joint" in ha["assumption"].lower())
    assert joint["agreement"] == "conflict"
    assert joint["severity"] == "fatal"  # highest wins
    # deepseek-only finding should be single_provider_only.
    deepseek_only = next(ha for ha in merged["hidden_assumptions"] if "preprocessing" in ha["assumption"])
    assert deepseek_only["agreement"] == "single_provider_only"
    # claude-only finding should be single_provider_only.
    claude_only = next(ha for ha in merged["hidden_assumptions"] if "cross-canopy" in ha["assumption"])
    assert claude_only["agreement"] == "single_provider_only"

    # needs_human_decision should include conflict + single-provider-fatal.
    nh_ids = {nh["id"] for nh in merged["needs_human_decision"] if nh["kind"] == "hidden_assumption"}
    assert joint["id"] in nh_ids  # conflict
    assert deepseek_only["id"] in nh_ids  # single-provider fatal escalates
    # claude_only is single_provider_only but only major severity, so not escalated.
    assert claude_only["id"] not in nh_ids

    assert md_out.exists()
    assert "Needs Human Decision" in md_out.read_text(encoding="utf-8")


def test_merge_adversaries_skips_manual_pending_inputs(tmp_path: Path) -> None:
    from review_council.adversary_merge import merge_adversaries

    primary = tmp_path / "primary.json"
    secondary = tmp_path / "secondary.json"
    _write_adversary(primary, provider="deepseek", hidden=[
        {"id": "MA-01", "assumption": "X fatal", "breakage": "y", "reported_check": "none", "severity": "fatal"}
    ])
    secondary.write_text(
        json.dumps({"source": "manual_pending", "case_id": "demo", "provider": "claude", "hidden_assumptions": [], "runs": []}),
        encoding="utf-8",
    )
    merged_out = tmp_path / "merged.json"
    merged = merge_adversaries([primary, secondary], merged_out)
    assert merged["providers"] == ["deepseek"]
    assert str(secondary) in merged["skipped_inputs"]
    # The deepseek finding is single_provider_only AND fatal -> escalates.
    assert merged["hidden_assumptions"][0]["agreement"] == "single_provider_only"
    nh_kinds = [nh["kind"] for nh in merged["needs_human_decision"]]
    assert "hidden_assumption" in nh_kinds


def test_merge_adversaries_claim_downgrades_always_escalate(tmp_path: Path) -> None:
    from review_council.adversary_merge import merge_adversaries

    primary = tmp_path / "primary.json"
    _write_adversary(
        primary,
        provider="deepseek",
        hidden=[],
        deps=[
            {"id": "HCD-01", "paper_claim": "N is the cross-scale prior", "depends_on_assumptions": ["MA-01"], "if_violated_downgrade_to": "soft form", "severity": "fatal"}
        ],
    )
    merged_out = tmp_path / "merged.json"
    merged = merge_adversaries([primary], merged_out)
    nh = merged["needs_human_decision"]
    assert any(item["kind"] == "headline_claim_dependency" for item in nh)


# --- plan absorbs merged adversary ---------------------------------------


def test_plan_consumes_merged_adversary_with_human_decision(tmp_path: Path) -> None:
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    merged = tmp_path / "reviews" / "methodology_adversary.merged.json"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"
    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)
    merged.parent.mkdir(parents=True, exist_ok=True)
    merged.write_text(
        json.dumps(
            {
                "case_id": "demo",
                "providers": ["deepseek", "claude"],
                "n_total_runs": 2,
                "hidden_assumptions": [
                    {
                        "id": "MERGE-A-01",
                        "assumption": "joint inversion identifiability not shown",
                        "breakage": "everything downstream depends on Optimal_N validity",
                        "reported_check": "none",
                        "severity": "fatal",
                        "agreement": "multi_provider",
                        "found_by": [
                            {"provider": "deepseek", "run_index": 1, "original_id": "MA-01"},
                            {"provider": "claude", "run_index": 1, "original_id": "HA-1"},
                        ],
                    }
                ],
                "unmet_research_goals": [],
                "headline_claim_dependencies": [
                    {
                        "id": "MERGE-HCD-01",
                        "paper_claim": "N is the cross-scale prior",
                        "depends_on_assumptions": ["MERGE-A-01"],
                        "if_violated_downgrade_to": "exploratory observation only",
                        "severity": "fatal",
                        "agreement": "multi_provider",
                    }
                ],
                "needs_human_decision": [
                    {"kind": "hidden_assumption", "id": "MERGE-A-01", "reason": "single provider raised as fatal — confirm before dropping"},
                    {"kind": "headline_claim_dependency", "id": "MERGE-HCD-01", "reason": "headline claim downgrade requires editorial judgment"},
                ],
            }
        ),
        encoding="utf-8",
    )

    from review_council.author_editorial import build_author_review_plan

    stats = build_author_review_plan(
        paper_shape_path=paper_shape,
        meta_comments_path=meta,
        detail_audit_path=detail,
        output_json_path=plan_json,
        output_md_path=plan_md,
        voice="senior_peer",
        api_key=None,
        methodology_adversary_path=merged,
    )
    assert stats["source"] == "offline"
    plan = json.loads(plan_json.read_text(encoding="utf-8"))
    must_keep_ids = {r.get("id") for r in plan["must_keep_strategic"]}
    assert "MERGE-A-01" in must_keep_ids
    assert "MERGE-HCD-01" in must_keep_ids
    # needs_human_decision must propagate through the plan.
    assert plan.get("human_decision_needed"), "merged adversary's human decisions must propagate into plan"
    nh_ids = [item["id"] for item in plan["human_decision_needed"]]
    assert "MERGE-A-01" in nh_ids
    assert "MERGE-HCD-01" in nh_ids


# --- rewrite redaction over cross-provider mentions ----------------------


def test_redaction_strips_claude_gpt_openai_mentions() -> None:
    from review_council.author_editorial import find_internal_tokens, redact_internal_tokens

    leaky = (
        "Claude says this fails. ChatGPT confirms. GPT-4 also flags. "
        "Anthropic and OpenAI both raised major concerns. Gemini agreed."
    )
    leaks = find_internal_tokens(leaky)
    assert any("Claude" in t for t in leaks)
    assert any("ChatGPT" in t for t in leaks)
    assert any("OpenAI" in t for t in leaks)
    assert any("Anthropic" in t for t in leaks)
    cleaned = redact_internal_tokens(leaky)
    for token in ["Claude", "ChatGPT", "GPT-4", "Anthropic", "OpenAI", "Gemini"]:
        assert token not in cleaned, f"{token} survived redaction: {cleaned}"
    assert find_internal_tokens(cleaned) == []


def test_rewrite_via_manual_provider_redacts_external_input(tmp_path: Path) -> None:
    """End-to-end: external rewrite produced by Claude is redacted before final write."""
    paper_shape = tmp_path / "reviews" / "paper_shape.md"
    meta = tmp_path / "comments" / "review_comments.meta.json"
    detail = tmp_path / "comments" / "detail_audit.json"
    plan_json = tmp_path / "comments" / "author_review_plan.json"
    plan_md = tmp_path / "comments" / "author_review_plan.md"
    source_map = tmp_path / "provenance" / "source_map.jsonl"
    template = tmp_path / "rewrite_tpl.md"
    output = tmp_path / "comments" / "author_facing_comments.md"
    external = tmp_path / "claude_response.md"

    _write_paper_shape(paper_shape)
    _write_meta_comments(meta)
    _write_detail_audit(detail)
    _write_source_map(source_map)
    template.write_text("rewrite prompt body for {voice}", encoding="utf-8")

    # Claude's response contains a couple of vendor mentions plus the body.
    external.write_text(
        "# 审稿意见\n\nClaude 这一段建议重组第四章。Anthropic 模型还提示 N 反演要补对照。\n\n"
        "## 总体修改方向\n1. 重组第四章\n2. 压缩第五章\n3. 反思 N\n",
        encoding="utf-8",
    )

    from review_council.author_editorial import build_author_review_plan, run_author_editorial_rewrite

    build_author_review_plan(
        paper_shape_path=paper_shape,
        meta_comments_path=meta,
        detail_audit_path=detail,
        output_json_path=plan_json,
        output_md_path=plan_md,
        voice="senior_peer",
        api_key=None,
    )

    stats = run_author_editorial_rewrite(
        paper_shape_path=paper_shape,
        plan_path=plan_json,
        meta_comments_path=meta,
        detail_audit_path=detail,
        source_map_path=source_map,
        output_md_path=output,
        voice="senior_peer",
        api_key=None,
        prompt_template=template,
        provider="manual",
        external_input=external,
    )
    assert stats["used_strong"] is True
    assert stats["provider"] == "manual"
    assert stats["leaks"] == []
    text = output.read_text(encoding="utf-8")
    assert "Claude" not in text
    assert "Anthropic" not in text
    assert "总体修改方向" in text  # body content survives


# --- workflow stage ordering ---------------------------------------------


def test_thesis_undergrad_workflow_includes_merge_stage_in_correct_order() -> None:
    workflows_dir = REPO_ROOT / "docs" / "workflows"
    wf = load_workflow(workflows_dir / "thesis_undergrad.yaml")
    ids = [stage.id for stage in wf.stages]
    assert "methodology_adversary" in ids
    assert "methodology_adversary_secondary" in ids
    assert "merge_methodology_adversaries" in ids
    assert "author_review_plan" in ids
    # merge must come after both adversary stages and before plan.
    assert ids.index("methodology_adversary") < ids.index("merge_methodology_adversaries")
    assert ids.index("methodology_adversary_secondary") < ids.index("merge_methodology_adversaries")
    assert ids.index("merge_methodology_adversaries") < ids.index("author_review_plan")
