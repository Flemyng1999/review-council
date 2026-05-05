"""Skill-style rubric loader.

Each rubric file under `rubrics/` carries YAML frontmatter declaring its
dimension, applicable layers, applicable case types, and a list of checks.
The loader selects rubrics by `(case_type, layer)` so prompts and aggregators
see only the items that apply to the current review unit.

Frontmatter is constrained: scalar values, flow lists, and a block list of
check dicts. PyYAML is intentionally not a dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DIMENSIONS = (
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
)

LAYERS = ("macro", "chapter", "section", "micro")

CASE_TYPES = ("journal", "thesis_undergrad", "thesis_master", "thesis_phd")


@dataclass(frozen=True)
class RubricCheck:
    id: str
    text: str
    severity_if_failed: str = "moderate"


@dataclass(frozen=True)
class Rubric:
    name: str
    dimension: str
    description: str
    applicable_layers: tuple[str, ...]
    applicable_case_types: tuple[str, ...]
    checks: tuple[RubricCheck, ...]
    body: str
    path: Path

    def applies(self, case_type: str, layer: str) -> bool:
        if self.applicable_case_types and case_type and case_type not in self.applicable_case_types:
            return False
        if self.applicable_layers and layer and layer not in self.applicable_layers:
            return False
        return bool(self.checks)


def parse_rubric(path: Path) -> Rubric:
    text = path.read_text(encoding="utf-8")
    front, body = _split_frontmatter(text)
    if front is None:
        raise ValueError(f"Rubric missing frontmatter: {path}")
    data = _parse_yaml(front)
    checks = tuple(
        RubricCheck(
            id=str(item.get("id", "")),
            text=str(item.get("text", "")),
            severity_if_failed=str(item.get("severity_if_failed", "moderate")),
        )
        for item in data.get("checks", [])
        if isinstance(item, dict) and item.get("id") and item.get("text")
    )
    return Rubric(
        name=str(data.get("name", path.stem)),
        dimension=str(data.get("dimension", "")),
        description=str(data.get("description", "")),
        applicable_layers=tuple(_as_list(data.get("applicable_layers"))),
        applicable_case_types=tuple(_as_list(data.get("applicable_case_types"))),
        checks=checks,
        body=body.strip(),
        path=path,
    )


def load_rubrics(rubrics_dir: Path) -> list[Rubric]:
    rubrics: list[Rubric] = []
    for path in sorted(rubrics_dir.glob("*.md")):
        try:
            rubrics.append(parse_rubric(path))
        except ValueError:
            continue
    return rubrics


def select_rubrics(
    rubrics_dir: Path,
    case_type: str,
    layer: str,
    dimensions: Iterable[str] | None = None,
) -> list[Rubric]:
    wanted = set(dimensions) if dimensions else None
    return [
        r
        for r in load_rubrics(rubrics_dir)
        if r.applies(case_type, layer) and (wanted is None or r.dimension in wanted)
    ]


def render_checks_block(rubrics: list[Rubric]) -> str:
    """Compact Markdown block listing every applicable check, ready for prompt injection."""

    lines: list[str] = []
    for r in rubrics:
        if not r.checks:
            continue
        lines.append(f"### {r.name} ({r.dimension})")
        for c in r.checks:
            lines.append(f"- [{c.id}] ({c.severity_if_failed}) {c.text}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end < 0:
        return None, text
    front = text[4:end]
    rest = text[end + 4 :]
    if rest.startswith("\n"):
        rest = rest[1:]
    return front, rest


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def parse_yaml_lite(text: str) -> dict:
    """Public alias of `_parse_yaml` for the constrained YAML subset."""

    return _parse_yaml(text)


def _parse_yaml(text: str) -> dict:
    """Parse a constrained YAML subset used by rubric and prompt frontmatter."""

    result: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if not line.startswith(" ") and ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest == "":
                items, consumed = _parse_block_list(lines, i + 1)
                result[key] = items
                i = consumed
                continue
            result[key] = _coerce_scalar(rest)
        i += 1
    return result


def _parse_block_list(lines: list[str], start: int) -> tuple[list, int]:
    """Parse a YAML block list. Accepts both indented and non-indented `- ` items."""

    items: list = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            break
        content = stripped[2:].strip()
        base_indent = len(line) - len(stripped)
        # Continuation lines must indent strictly past `- ` (base_indent + 2).
        continuation_floor = base_indent + 2
        if ":" in content and not content.startswith("["):
            item: dict = {}
            k, _, v = content.partition(":")
            item[k.strip()] = _coerce_scalar(v.strip())
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                ns = nxt.lstrip()
                ni = len(nxt) - len(ns)
                if ni < continuation_floor or ns.startswith("- "):
                    break
                if ":" in ns:
                    nk, _, nv = ns.partition(":")
                    item[nk.strip()] = _coerce_scalar(nv.strip())
                j += 1
            items.append(item)
            i = j
            continue
        items.append(_coerce_scalar(content))
        i += 1
    return items, i


def _coerce_scalar(value: str) -> object:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [_strip_quotes(s.strip()) for s in inner.split(",") if s.strip()]
    return _strip_quotes(value)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value
