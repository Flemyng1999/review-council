"""Validation for review case directories."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from review_council.case.manifest import CASE_TYPES, THESIS_FORMATS
from review_council.case.paths import CASE_DIRS

REQUIRED_FILES = (
    "case.md",
    "manifest.yaml",
    "retrospective.md",
    "evidence/claim_evidence_matrix.json",
    "reviews/primary.md",
    "reviews/bsc_thesis_review.md",
    "reviews/dissent.md",
    "comments/review_comments.json",
    "decision/editorial_judgment.md",
)

MANIFEST_KEYS = (
    "case_id:",
    "case_type:",
    "status:",
    "source_files:",
    "normalized_files:",
    "processing:",
    "review:",
    "decision:",
)

_VALUE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_case(case_path: Path) -> ValidationResult:
    result = ValidationResult()
    if not case_path.exists():
        result.errors.append(f"Case path does not exist: {case_path}")
        return result
    if not case_path.is_dir():
        result.errors.append(f"Case path is not a directory: {case_path}")
        return result

    for directory in CASE_DIRS:
        if not (case_path / directory).is_dir():
            result.errors.append(f"Missing directory: {directory}")

    for file_name in REQUIRED_FILES:
        if not (case_path / file_name).is_file():
            result.errors.append(f"Missing file: {file_name}")

    manifest_path = case_path / "manifest.yaml"
    if manifest_path.exists():
        text = manifest_path.read_text(encoding="utf-8")
        for key in MANIFEST_KEYS:
            if key not in text:
                result.errors.append(f"manifest.yaml missing key: {key}")
        _validate_case_type(text, result)
    else:
        result.errors.append("Missing file: manifest.yaml")

    source_files = [path for path in (case_path / "source").rglob("*") if path.is_file()]
    if not source_files:
        result.warnings.append("source/ contains no manuscript files")
    return result


def _validate_case_type(text: str, result: ValidationResult) -> None:
    values = _scalar_values(text)
    case_type = values.get("case_type", "")
    if case_type and case_type not in CASE_TYPES:
        result.errors.append(f"manifest.yaml case_type unknown: {case_type!r}")
        return
    thesis_format = values.get("thesis_format", "")
    if case_type == "thesis_phd":
        if thesis_format not in THESIS_FORMATS:
            result.errors.append(
                "manifest.yaml thesis_phd requires thesis_format in "
                f"{THESIS_FORMATS}; got {thesis_format!r}"
            )
    elif thesis_format and thesis_format not in THESIS_FORMATS:
        result.errors.append(f"manifest.yaml thesis_format unknown: {thesis_format!r}")


def _scalar_values(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith(" "):
            continue
        match = _VALUE_RE.match(line)
        if match and match.group(2) and not match.group(2).startswith("["):
            out[match.group(1)] = match.group(2).strip().strip("'\"")
    return out
