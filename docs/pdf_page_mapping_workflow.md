# Frozen-PDF Page Mapping Workflow

Purpose: produce author-facing review comments with stable page numbers while
keeping the review text in normalized Markdown.

## Principle

DOCX, TeX, and Markdown line numbers are editing coordinates. Author-facing
review needs publication coordinates. Therefore, every review case should keep a
frozen PDF snapshot and map normalized Markdown anchors back to that PDF.

## Case Layout

```text
cases/<case-id>/
  source/
    manuscript.docx
  frozen/
    manuscript.pdf
  normalized/
    manuscript.md
  provenance/
    source_map.jsonl
```

`frozen/manuscript.pdf` is the page-coordinate authority for comments. The
Markdown file remains the review-coordinate authority for AI analysis.

## Commands

Freeze DOCX to PDF when LibreOffice/soffice is available:

```bash
PYTHONPATH=src python -m review_council.cli freeze-docx \
  cases/<case-id>/source/manuscript.docx \
  cases/<case-id>/frozen/manuscript.pdf
```

Convert DOCX to Markdown with Pandoc:

```bash
pandoc cases/<case-id>/source/manuscript.docx \
  --extract-media=cases/<case-id>/normalized/media \
  -t gfm \
  -o cases/<case-id>/normalized/manuscript.md
```

Map Markdown lines to frozen PDF pages:

```bash
PYTHONPATH=src python -m review_council.cli map-pdf-pages \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/frozen/manuscript.pdf \
  cases/<case-id>/provenance/source_map.jsonl
```

Render comments:

```bash
PYTHONPATH=src python -m review_council.cli render-comments \
  cases/<case-id>/comments/review_comments.json \
  cases/<case-id>/provenance/source_map.jsonl \
  cases/<case-id>/comments/author_facing_comments.md
```

## Current Limitation

The current PDF mapper infers page numbers by matching normalized Markdown
lines against extracted PDF page text. It is good enough to replace `p. ?` with
page numbers for many comments, but it does not yet produce true PDF
page-local line numbers. Rendered comments therefore use:

```text
p. <page>, normalized line <line>
```

For formal delivery, manually spot-check comments whose exact page matters.
