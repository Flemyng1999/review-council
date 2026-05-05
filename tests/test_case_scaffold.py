import json
from pathlib import Path

import pytest

from review_council.case.manifest import CaseManifest
from review_council.case.paths import create_case
from review_council.case.validate import validate_case
from review_council.comments import render_comments
from review_council.config import get_config_value, load_env_file
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
    link_issues_to_claims,
    load_claim_matrix,
    render_claim_matrix_md,
    save_claim_matrix,
)
from review_council.comment_synthesis import _apply_severity_caps, synthesize_comments
from review_council.meta_review import backfill_anchors, split_meta_review_response
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
    severities = [c["severity"] for c in comments]
    assert severities == ["blocking", "major", "moderate"]
    assert stats["kept_comments"] == 3
    assert stats["input_issues"] == 5
    moderate = next(c for c in comments if c["severity"] == "moderate")
    assert sorted(moderate["derived_from_issues"]) == ["ISS-0003", "ISS-0004"]


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


def test_render_comments_hides_provenance_by_default(tmp_path: Path) -> None:
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
                    "derived_from_issues": ["ISS-0007"],
                    "linked_claims": ["CLM-0003"],
                }
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out.md"
    from review_council.comments import render_comments as render

    render(comments, source_map, output)
    rendered = output.read_text(encoding="utf-8")
    assert "Provenance" not in rendered
    assert "ISS-0007" not in rendered

    render(comments, source_map, output, show_provenance=True)
    rendered = output.read_text(encoding="utf-8")
    assert "Provenance" in rendered
    assert "ISS-0007" in rendered


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
