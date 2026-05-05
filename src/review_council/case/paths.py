"""Canonical paths for review cases."""

from __future__ import annotations

import shutil
from pathlib import Path

from review_council.case.manifest import CaseManifest

CASE_DIRS = (
    "source",
    "source/supplementary",
    "normalized",
    "normalized/figures",
    "normalized/tables",
    "provenance",
    "units",
    "units/appendix",
    "evidence",
    "evidence/cited_sources",
    "reviews",
    "comments",
    "decision",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_cases_root() -> Path:
    return repo_root() / "cases"


def template_path(name: str) -> Path:
    return repo_root() / "templates" / name


def create_case(case_id: str, cases_root: Path, manifest: CaseManifest) -> Path:
    case_path = cases_root / case_id
    case_path.mkdir(parents=True, exist_ok=False)

    for directory in CASE_DIRS:
        (case_path / directory).mkdir(parents=True, exist_ok=True)

    (case_path / "manifest.yaml").write_text(manifest.to_yaml(), encoding="utf-8")
    _copy_template("case.md", case_path / "case.md")
    _copy_template("claim_evidence_matrix.json", case_path / "evidence" / "claim_evidence_matrix.json")
    _copy_template("reviewer_report.md", case_path / "reviews" / "primary.md")
    _copy_template("bsc_thesis_review.md", case_path / "reviews" / "bsc_thesis_review.md")
    _copy_template("dissent_review.md", case_path / "reviews" / "dissent.md")
    _copy_template("review_comments.json", case_path / "comments" / "review_comments.json")
    _copy_template("editorial_judgment.md", case_path / "decision" / "editorial_judgment.md")
    _copy_template("retrospective.md", case_path / "retrospective.md")
    return case_path


def _copy_template(template_name: str, destination: Path) -> None:
    source = template_path(template_name)
    if source.exists():
        shutil.copyfile(source, destination)
    else:
        destination.write_text("", encoding="utf-8")
