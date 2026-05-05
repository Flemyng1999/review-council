# BSc Thesis Pilot Review Workflow

Purpose: review one undergraduate thesis with the current review-council
framework, while recording what must become a future Skill.

The end-to-end stage runner is `python -m review_council.cli review-case
cases/<case-id>`, driven by
[docs/workflows/thesis_undergrad.yaml](thesis_undergrad.yaml). This Markdown
file is the human-readable companion to that recipe; the YAML is the truth
the runner consumes.

## Target

This workflow is for undergraduate theses in vegetation quantitative remote
sensing, remote sensing, agriculture, or environmental physics.

It does not judge the work by journal-publication standards. The primary
question is whether the thesis demonstrates bounded research literacy,
technically correct execution, honest interpretation, and clear reporting.

## Inputs

- `source/<thesis>.docx`, `source/<thesis>.tex`, or `source/<thesis>.pdf`
- `frozen/manuscript.pdf` when page-stable author comments are needed
- optional school rubric or thesis requirements
- optional supervisor priorities

## Outputs

- `normalized/manuscript.md`
- `provenance/source_map.jsonl`
- `reviews/bsc_thesis_review.md`
- `comments/review_comments.json`
- `comments/author_facing_comments.md`
- `decision/editorial_judgment.md`
- `retrospective.md`

## Fixed Workflow

### Step 0 - Create Case

```bash
PYTHONPATH=src python -m review_council.cli init-case <case-id>
```

Place the thesis file under:

```text
cases/<case-id>/source/
```

Concrete case directories are ignored by Git.

### Step 1 - Normalize Manuscript

The canonical route is `source -> frozen/manuscript.pdf -> MinerU -> normalized/manuscript.md`.
See `docs/paper_ingestion_protocol.md` for rationale.

For DOCX source, export the manuscript to PDF from Microsoft Word and save the
exported file as `cases/<case-id>/frozen/manuscript.pdf`. Pandoc DOCX -> Markdown is not
supported (breaks equations); `freeze-docx` (LibreOffice) is a fallback only.

For native PDF source, copy or symlink the PDF to
`cases/<case-id>/frozen/manuscript.pdf`.

Then run MinerU on the Linux GPU host:

```bash
ssh ubuntu-303 -p 5422
cd ~/Code/review-council
bash scripts/mineru_case_extract.sh \
  cases/<case-id>/frozen/manuscript.pdf \
  cases/<case-id>
```

This produces `normalized/manuscript.md`, `normalized/<stem>.assets/`, and a
fallback `provenance/source_map.jsonl`.

### Step 2 - Build Source Map

If the converter did not create a richer source map:

```bash
PYTHONPATH=src python -m review_council.cli index-markdown \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/provenance/source_map.jsonl
```

If a frozen PDF exists, map Markdown line anchors to PDF pages instead:

```bash
PYTHONPATH=src python -m review_council.cli map-pdf-pages \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/frozen/manuscript.pdf \
  cases/<case-id>/provenance/source_map.jsonl
```

### Step 3 - First-Pass Triage

Build hierarchical units before review:

```bash
PYTHONPATH=src python -m review_council.cli build-units \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/units
```

Then read the manuscript at whole-paper level:

- topic and scope;
- structure completeness;
- whether the method is basically appropriate;
- whether the main conclusion is supported;
- likely top 3 problems.

Write to:

```text
reviews/hierarchical_review.md
```

### Step 4 - Layered Deep Review

Review at multiple granularities:

- whole manuscript: central thesis, contribution, story, target fit;
- chapters: role in the whole argument;
- sections: methods, evidence, variables, validation, citations, units;
- micro pass: wording, numbering, figure/table labels, obvious typos.

Use DeepSeek for coverage on macro/chapter/high-risk section units:

```text
reviews/deepseek/<layer>/<unit>.json
```

Example:

```bash
PYTHONPATH=src python -m review_council.cli deepseek-review-unit \
  cases/<case-id>/units/<unit>.md \
  cases/<case-id>/reviews/deepseek/<unit>.json \
  --case-id <case-id> \
  --unit-id <unit>
```

Treat this as issue discovery. A stronger meta-review and human check still
decide which comments survive.

Record synthesized comments in:

```text
reviews/hierarchical_review.md
reviews/meta_review.md
comments/review_comments.json
```

### Step 5 - Remote-Sensing Technical Check

For this domain, check at least:

- data source and acquisition date;
- sensor/platform and bands;
- preprocessing and masking;
- sample/reference data quality;
- validation method;
- metrics and uncertainty;
- figure/table interpretability;
- whether conclusions overreach the evidence.

### Step 6 - Dissent Pass

Force one short dissent or meta-review:

- What is the strongest reason this thesis might be over-rated?
- What is the strongest reason it might be under-rated?
- Which criticism would most help the student improve?

### Step 7 - Render Author-Facing Comments

```bash
PYTHONPATH=src python -m review_council.cli render-comments \
  cases/<case-id>/comments/review_comments.json \
  cases/<case-id>/provenance/source_map.jsonl \
  cases/<case-id>/comments/author_facing_comments.md
```

### Step 8 - Human Judgment

The human reviewer decides:

- overall assessment;
- required revisions;
- optional improvements;
- what feedback is fair and useful for an undergraduate student.

AI-generated critiques are inputs, not final judgment.

### Step 9 - Retrospective

After the pilot, fill:

```text
retrospective.md
templates/framework_application_record.md
```

Focus on:

- what the workflow caught;
- what it missed;
- whether DOCX/PDF conversion preserved enough anchors;
- what should become a future Skill instruction.

## BSc Review Emphasis

Increase weight:

- clear problem statement;
- correct basic method;
- careful data handling;
- honest interpretation;
- complete thesis structure;
- useful improvement feedback.

Decrease weight:

- high novelty;
- journal-level significance;
- broad transferability;
- publication polish.

## Non-Negotiable Problems

These remain serious even for undergraduate work:

- fabricated or unverifiable data;
- uncredited copying;
- method fundamentally unrelated to the research question;
- conclusions unsupported by results;
- severe citation misuse;
- misleading figures or metrics.
