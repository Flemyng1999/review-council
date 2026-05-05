"""Prompt template rendering.

Templates may carry Skill-style YAML frontmatter (`name`, `description`,
`applicable_case_types`, etc.) used by the loader and humans. The renderer
strips it before substitution so frontmatter never reaches the model.
"""

from __future__ import annotations

from pathlib import Path


def render_prompt_template(
    template_path: Path,
    values: dict[str, str],
    strip_frontmatter: bool = True,
) -> str:
    text = template_path.read_text(encoding="utf-8")
    if strip_frontmatter:
        text = _strip_frontmatter(text)
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    rest = text[end + 4 :]
    return rest.lstrip("\n")
