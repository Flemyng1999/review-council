# Paper Ingestion Protocol

The ingestion pipeline converts heterogeneous manuscript sources into a single
review-ready case structure. **The PDF is the canonical artifact.** Every
review case must terminate ingestion at:

```text
cases/<case-id>/frozen/manuscript.pdf
cases/<case-id>/normalized/manuscript.md
cases/<case-id>/normalized/<stem>.assets/
cases/<case-id>/provenance/source_map.jsonl
```

`frozen/manuscript.pdf` provides stable page anchors for author-facing
comments. `normalized/manuscript.md` is the machine-readable copy that
downstream stages (`build-units`, DeepSeek, aggregation) operate on.

## Canonical Routes

There is one canonical route. It does not depend on the source format:

```text
source (DOCX or native PDF)
  -> frozen/manuscript.pdf      # the page-stable copy
  -> MinerU on Linux GPU        # PDF -> Markdown + assets
  -> normalized/manuscript.md   # plus normalized/<stem>.assets/
  -> provenance/source_map.jsonl
```

### DOCX source

1. Open the DOCX in Microsoft Word and **export to PDF from Word**. Save the
   exported PDF as `cases/<case-id>/frozen/manuscript.pdf`.
2. Run MinerU on `frozen/manuscript.pdf` (see `docs/MinerU使用指南.md`).
3. The script writes `normalized/manuscript.md`, the asset folder, and a
   fallback `provenance/source_map.jsonl`.

Why Word export instead of pandoc DOCX → Markdown: pandoc breaks equations
and many figure/table layouts when DOCX uses Word's equation editor or
SmartArt. Word's own PDF export preserves equation rendering, and MinerU
recovers the structure from that PDF more reliably than pandoc recovers it
from DOCX. Direct DOCX → Markdown via pandoc is therefore not a supported
route for review production.

`review-council freeze-docx` (LibreOffice fallback) is retained only for
environments without Word. Its PDF output renders equations less reliably
than Word's export. Use it only when a Word-exported PDF cannot be obtained,
and document the choice in `manifest.yaml`.

### Native PDF source

1. Place the PDF at `cases/<case-id>/source/<filename>.pdf`.
2. Copy or symlink it to `cases/<case-id>/frozen/manuscript.pdf` (the source
   PDF is itself the page-stable copy).
3. Run MinerU on `frozen/manuscript.pdf`.

### TeX source

TeX is currently a future route. The intended canonical path is
`TeX → LaTeX-built PDF → MinerU → normalized/manuscript.md`, mirroring the
DOCX route. Until that path is implemented, treat TeX manuscripts as native
PDF sources by building the PDF locally first.

## Required Outputs

```text
cases/<case-id>/
├── source/                         # original DOCX, TeX, or native PDF
├── frozen/manuscript.pdf           # page-stable PDF, anchors for the author
├── normalized/manuscript.md        # MinerU output
├── normalized/<stem>.assets/       # MinerU images, content list, layout PDF
├── provenance/source_map.jsonl     # anchor map (Markdown line / PDF page)
├── units/                          # built by `build-units`
├── reviews/                        # AI reviews and meta-review
├── comments/                       # author-facing comments
└── decision/                       # human editorial judgment
```

## Provenance Record Shape

```json
{
  "anchor_id": "L00042",
  "normalized_path": "cases/<case-id>/normalized/manuscript.md",
  "normalized_line_start": 42,
  "normalized_line_end": 42,
  "source_path": "cases/<case-id>/frozen/manuscript.pdf",
  "source_page": 3,
  "source_line_start": null,
  "source_line_end": null,
  "text": "..."
}
```

`source_path` is the frozen PDF for both DOCX and native-PDF cases. Page
anchors come from MinerU's `*_content_list.json` and `*_middle.json` inside
`normalized/<stem>.assets/`. The `index-markdown` command can produce a
fallback source map when MinerU's layout JSON is unavailable; in that case
`source_page` will be empty and the limitation must be recorded in the
manifest or retrospective.

## Author-Facing Comment Generation

```bash
PYTHONPATH=src python -m review_council.cli render-comments \
  cases/<case-id>/comments/review_comments.json \
  cases/<case-id>/provenance/source_map.jsonl \
  cases/<case-id>/comments/author_facing_comments.md
```

The renderer prefers explicit `page` / `line_start` / `line_end` fields in
the comment, then falls back to `source_map.jsonl` lookups by `anchor_id`.

## Policy

- The frozen PDF is the page-anchor authority. Comments must cite pages from
  it, not visual line numbers from a Word document.
- Lossy conversion is allowed only when it is recorded in `manifest.yaml` or
  `retrospective.md`. Silent loss is a review-system bug.
- DOCX → pandoc → Markdown is not a supported review route. Equations and
  layouts are recoverable only from a high-fidelity PDF.
- MinerU runs on the Linux GPU host (`ubuntu-303`). The Mac side does not
  run MinerU; it only consumes its outputs.
