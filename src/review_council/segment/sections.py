"""Simple Markdown section splitter."""

from __future__ import annotations


def split_markdown_sections(markdown: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current).strip())
    return [section for section in sections if section]
