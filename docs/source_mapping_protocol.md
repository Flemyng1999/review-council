# Source Mapping Protocol

Purpose: make review comments traceable back to source pages and lines.

## Problem

Review comments need author-facing locations such as:

```text
p. 7, lines 12-16
```

But DOCX, TeX, PDF, Markdown, and AI review units do not share one native line
coordinate system. Word reflows lines depending on fonts and layout. TeX has
source lines but rendered PDF pages. PDF has pages and layout boxes but no
semantic source lines. Therefore line/page comments must be generated from an
explicit source map, not guessed after review.

## Core Rule

Every ingestion route must produce:

```text
cases/<case-id>/provenance/source_map.jsonl
```

Every review comment should point to `anchor_id`. Page/line numbers are rendered
from the source map at the end.

## Route A: DOCX -> Pandoc -> Markdown

Recommended path:

```text
source/manuscript.docx
  -> pandoc
  -> normalized/manuscript.md
  -> provenance/source_map.jsonl
```

DOCX does not have stable source line numbers. For author-facing line numbers,
use one of these:

1. Export DOCX to a frozen review PDF with line numbers, then map comments to
   that PDF.
2. Use normalized Markdown line numbers as the review coordinate system.
3. If required by an institution, return comments by section/paragraph instead
   of pretending Word visual lines are stable.

## Route B: TeX -> Pandoc -> Markdown

Recommended path:

```text
source/latex_project/
  -> pandoc
  -> normalized/manuscript.md
  -> provenance/source_map.jsonl
```

TeX can support stronger provenance:

- TeX source file and line numbers;
- rendered PDF page numbers;
- optional SyncTeX-based source-to-PDF mapping.

For author-facing comments, prefer rendered PDF page/line if the author will
read the PDF; include TeX source line only when the author is expected to revise
the TeX source directly.

## Route C: PDF -> MinerU -> Markdown

Recommended path:

```text
source/manuscript.pdf
  -> MinerU
  -> normalized/manuscript.md
  -> normalized/<stem>.assets/
  -> provenance/source_map.jsonl
```

MinerU preserves page and layout intermediates such as content-list and middle
JSON files. These should be kept under `normalized/` or `provenance/` because
they are the best available bridge from Markdown text back to PDF page regions.

PDF line anchors are OCR/layout-derived. They are useful but must be treated as
lower-confidence than controlled DOCX/TeX source anchors.

## Comment Record Schema

Use JSON for machine rendering:

```json
{
  "id": "CMT-001",
  "severity": "major",
  "anchor_id": "L00042",
  "page": 7,
  "line_start": 12,
  "line_end": 16,
  "quote": "The manuscript claims ...",
  "comment": "This conclusion is not supported by the validation design.",
  "recommendation": "Add an independent validation set or narrow the claim."
}
```

Manual page/line overrides are allowed. They should be used when a human checks
the final exported PDF and corrects the automatic location.

## Generated Author File

The final author-facing file should be:

```text
cases/<case-id>/comments/author_facing_comments.md
```

Optional later exports:

- DOCX with comments;
- PDF annotation summary;
- institution-specific review form.

## Current Implementation

The current package implements:

```bash
PYTHONPATH=src python -m review_council.cli index-markdown \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/provenance/source_map.jsonl

PYTHONPATH=src python -m review_council.cli render-comments \
  cases/<case-id>/comments/review_comments.json \
  cases/<case-id>/provenance/source_map.jsonl \
  cases/<case-id>/comments/author_facing_comments.md
```

This is a fallback line-map implementation. Rich DOCX/TeX/PDF importers should
replace it with page-aware source maps.
