"""Manifest model for a review case.

The manifest writer is intentionally dependency-free; it emits a constrained
YAML subset by string composition. Readers parse the same subset.

`case_type` and the optional `thesis_format` and `discipline` fields are the
discriminators that the rubric loader, prompt selector, and stage runner read
to decide what applies to this case.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CASE_TYPES = ("journal", "thesis_undergrad", "thesis_master", "thesis_phd")
THESIS_FORMATS = ("monograph", "cumulative")


@dataclass(frozen=True)
class CaseManifest:
    case_id: str
    title: str = ""
    case_type: str = "journal"
    thesis_format: str = ""
    discipline: str = ""
    source_files: list[str] = field(default_factory=list)
    normalized_files: list[str] = field(default_factory=list)
    status: str = "initialized"

    def __post_init__(self) -> None:
        if self.case_type not in CASE_TYPES:
            raise ValueError(f"Unknown case_type: {self.case_type!r}")
        if self.case_type == "thesis_phd":
            if self.thesis_format not in THESIS_FORMATS:
                raise ValueError(
                    "thesis_phd requires thesis_format in "
                    f"{THESIS_FORMATS}, got {self.thesis_format!r}"
                )
        elif self.thesis_format and self.thesis_format not in THESIS_FORMATS:
            raise ValueError(f"Unknown thesis_format: {self.thesis_format!r}")

    def to_yaml(self) -> str:
        return "\n".join(
            [
                f"case_id: {self.case_id}",
                f"title: {self.title!r}",
                f"case_type: {self.case_type}",
                f"thesis_format: {self.thesis_format}",
                f"discipline: {self.discipline}",
                f"status: {self.status}",
                "source_files:",
                *[f"  - {path}" for path in self.source_files],
                "normalized_files:",
                *[f"  - {path}" for path in self.normalized_files],
                "processing:",
                "  ingestion: pending",
                "  normalization: pending",
                "  segmentation: pending",
                "  evidence_extraction: pending",
                "review:",
                "  primary: pending",
                "  verifier: pending",
                "  dissent: pending",
                "  synthesis: pending",
                "  integrity_check: pending",
                "decision:",
                "  owner: ''",
                "  status: pending",
                "",
            ]
        )
