# Integrity Norms

Cross-cutting norms that apply independently of dimension scores. Failing any
of these invalidates dimension judgments rather than reducing them.

## Reviewer Ethics (COPE)

- Confidentiality: review materials are not used or disclosed beyond the
  review.
- Conflicts of interest: financial, personal, or academic competition
  declared up front.
- Objectivity: arguments substantiated, not asserted.
- Timeliness: silent delay is an integrity issue, not a logistical issue.
- Misconduct vigilance: plagiarism, image manipulation, duplicate
  publication, undeclared data reuse.

## Content Over Prestige (DORA)

- Do not use journal impact factor, conference rank, or institution name as
  a substitute for reading the work.
- Evaluate the manuscript or thesis on its own content, including data and
  software outputs, not on its publication venue.

## AI Tool Disclosure (ICMJE 2026 logic)

- Writing-assistance use disclosed in acknowledgments.
- Data analysis, classification, code generation, and figure generation use
  disclosed in methods.
- AI cannot be listed as an author. AI cannot own judgment. See
  `PROJECT.md`.

## Academic Norms (China MOE undergraduate sampling, applied generally)

For thesis cases especially, the following must be checked as integrity
artifacts, not folded into writing-quality feedback:

- Citation hygiene: quotations, paraphrases, and figure reuses traceable to
  sources, with permissions where required.
- Plagiarism check: similarity report (Chinese and English where relevant);
  matches above thresholds investigated, not auto-explained away.
- Fabrication red flags: writing style discontinuities, professional
  capability mismatched to artifact complexity, missing raw data, missing
  code version history.
- Training cycle completion (`thesis_undergrad`): explicit artifacts for
  problem framing, literature, data, analysis, and writing; gaps recorded
  in dissent.
- Mentor log: supervision interactions and the candidate's response to
  feedback summarized in `templates/mentor_voice.md` (when introduced).

## Anti-Sycophancy Posture

Doctoral examiners default to pass. Journal reviewers default to reject.
Both produce distinct sycophancy risks.

- Dissent artifact required for every case type.
- For thesis cases, the dissent reviewer must state the most specific
  concrete reason the work would fail if it were to fail. Soft critique is
  not sufficient.
- Synthesis may overrule dissent, but only by recording the reason in the
  decision record (`docs/dissent_rules.md`,
  `docs/decision_record_format.md`).

## Judgment Ownership

- Mentor voice: human-only.
- Final editorial decision: human-only, signed.
- AI critiques are inputs. Adopted, rejected, and unresolved critiques are
  distinguished in the decision record.

## Data and Code Norms (FAIR / FAIR4RS)

- Data: persistent identifier, version, license, accessible format.
- Code: source repository, release tag, DOI (e.g. Zenodo), license,
  dependency lock.
- Reference data: provenance chain, calibration history, scale-matching
  method to satellite footprint.
