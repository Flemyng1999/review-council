# Pandoc Ingestion (Deprecated for DOCX)

Pandoc is **not** the canonical ingestion tool for review cases. The
canonical route is `source -> frozen/manuscript.pdf -> MinerU -> normalized
Markdown`. See `docs/paper_ingestion_protocol.md` and
`docs/MinerU使用指南.md`.

## DOCX

DOCX → pandoc → Markdown is not supported for production review. Pandoc
silently drops or corrupts:

- Word equation editor formulas;
- many cross-references and footnotes;
- figure groupings and SmartArt;
- tracked changes and review comments.

The canonical DOCX route is:

1. Export the DOCX to PDF from Microsoft Word.
2. Run MinerU on the exported PDF (see `docs/MinerU使用指南.md`).

If Word is unavailable, `review-council freeze-docx` uses LibreOffice as a
fallback PDF builder. Its equation rendering is weaker than Word's export
and the choice must be noted in `manifest.yaml`.

## TeX

TeX → pandoc remains a stopgap until the LaTeX → PDF → MinerU route is
wired. For TeX cases today, the recommended path is to build the PDF
locally and then treat the case as a native-PDF source:

```bash
pdflatex main.tex
cp main.pdf cases/<case-id>/frozen/manuscript.pdf
bash scripts/mineru_case_extract.sh \
  cases/<case-id>/frozen/manuscript.pdf \
  cases/<case-id>
```

The pandoc TeX shortcut below is kept for low-stakes triage only:

```bash
pandoc cases/<case-id>/source/main.tex \
  --bibliography=cases/<case-id>/source/references.bib \
  -t gfm \
  -o cases/<case-id>/normalized/manuscript.md
PYTHONPATH=src python -m review_council.cli index-markdown \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/provenance/source_map.jsonl
```

This produces a Markdown-line-only source map. Author-facing comments must
be marked as Markdown-line anchored, not page anchored, when this route is
used.

## Policy

- Pandoc is not trusted for DOCX in this repository.
- Any pandoc-only conversion must be recorded in `manifest.yaml` or
  `retrospective.md`.
- Use the canonical PDF + MinerU route whenever feasible.
