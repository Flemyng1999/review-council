# review-council
Structured human-AI peer review with evidence, dissent, and accountable judgment.

`review-council` is a human-AI peer review production system. It turns a
manuscript and its attachments into a traceable review case: source files,
normalized text, reviewable units, evidence records, role-specific reviews,
dissent, human editorial judgment, and retrospective lessons.

## Core Rule

AI may generate critique. Human reviewers own judgment.

## Repository Shape

```text
cases/<case-id>/
├── source/       # original DOCX, TeX, PDF, figures, supplements
├── frozen/       # stable PDF snapshot for author-facing page anchors
├── normalized/   # converted review-ready manuscript artifacts
├── units/        # section or claim-level review units
├── evidence/     # claim/evidence matrices and source anchors
├── reviews/      # primary, verifier, dissent, and synthesis reviews
├── decision/     # human-owned editorial judgment
└── retrospective.md
```

Reusable code lives in `src/review_council/`; protocols live in `docs/`;
rubrics live in `rubrics/`; copyable case artifacts live in `templates/`.

## Quick Start

```bash
python -m review_council.cli init-case demo_001
python -m review_council.cli validate-case cases/demo_001
```

Canonical case commands:

```bash
python -m review_council.cli init-case demo_001 --case-type thesis_undergrad --discipline remote_sensing
# Place source under cases/demo_001/source/, then either:
#   - DOCX: export to PDF from Microsoft Word -> save as frozen/manuscript.pdf
#   - PDF:  copy or symlink source/<file>.pdf to frozen/manuscript.pdf
# Then run MinerU on the Linux GPU host:
ssh ubuntu-303 -p 5422
bash scripts/mineru_case_extract.sh cases/demo_001/frozen/manuscript.pdf cases/demo_001
# Back on any machine, run the full workflow:
python -m review_council.cli review-case cases/demo_001
# Inspect what runs:
python -m review_council.cli review-case cases/demo_001 --list
python -m review_council.cli list-rubrics --case-type thesis_undergrad --layer section
```

DOCX -> Markdown via pandoc is not supported (breaks equations). The
canonical route is `source -> frozen/manuscript.pdf -> MinerU ->
normalized/manuscript.md`. See [docs/paper_ingestion_protocol.md](docs/paper_ingestion_protocol.md)
and [docs/MinerU使用指南.md](docs/MinerU使用指南.md).

Other key docs: [docs/review_framework.md](docs/review_framework.md) for the
dimension and case-type taxonomy, [docs/case_types.md](docs/case_types.md)
for thresholds and roles, [docs/integrity_norms.md](docs/integrity_norms.md)
for gating norms, and [docs/workflows/](docs/workflows/) for the YAML
recipes the stage runner consumes.

During development:

```bash
python -m pip install -e ".[dev]"
pytest
```
