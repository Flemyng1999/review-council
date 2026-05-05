# GAPS.md - Open System Gaps

This file tracks flaws in the review system itself.

## GAP-001 - Format Conversion Fidelity

Status: open

DOCX, TeX, and PDF sources do not preserve the same structure. Figures, tables,
citations, equations, comments, and supplementary files need traceable handling.

Acceptance direction: every normalized unit should point back to its source file
and, where possible, source location.

## GAP-002 - AI Sycophancy in Review

Status: open

AI reviewers may over-agree with the author, the user, or earlier reviewers.

Acceptance direction: dissent roles and verification passes must be explicit,
not optional prose style.

## GAP-003 - Judgment Ownership

Status: open

The system must keep critique generation separate from editorial judgment.

Acceptance direction: decision files must record the human owner of the final
judgment and distinguish adopted, rejected, and unresolved AI critiques.

## GAP-004 - Evidence Strength Calibration

Status: open

Rubric scores can look precise while hiding weak evidence.

Acceptance direction: claim-level evidence records should carry source anchors,
strength labels, and uncertainty notes.

## GAP-005 - Causal and Attribution Self-Check Missing

Status: open

Manuscripts in vegetation remote sensing, agronomy, and environmental physics
routinely make causal or attribution claims (irrigation drives yield, drought
causes ET decline, sensor bias arises from cloud contamination) without
distinguishing them from statistical association.

Acceptance direction: when an issue's `dimension` is `evidence` and the claim
is causal, reviewers must record a Bradford Hill self-check (strength,
consistency, temporality, dose-response, plausibility, coherence). Absence of
the self-check should be flagged automatically by the meta-reviewer.

## GAP-006 - CEOS LPV Validation Stage Misstatement

Status: open

Authors frequently describe Stage 1 work (small site set, limited time) as
"global validation" or "operational validation" (Stage 4). The system has no
automated check that the claimed validation stage matches the evidence.

Acceptance direction: the integrity check or methodology rubric must require
authors to declare a CEOS LPV stage (1-4) and the meta-reviewer must verify
that the declared stage is supported by sample-set size, geographic spread,
temporal span, and reference-data quality.

## GAP-007 - Thesis Examiner Default-Pass Posture Not Counter-Weighted

Status: open

Mullins & Kiley document that doctoral examiners default to pass and read
with sympathy; this is the inverse of journal review's default-reject posture.
Without an intensified dissent role, AI reviewers inherit the default-pass
sycophancy when case_type is `thesis_*`.

Acceptance direction: dissent prompts must dispatch by case_type
(`dissent_journal` vs `dissent_thesis`), and `dissent_thesis` must require a
"most specific concrete reason this thesis would fail" answer with anchored
evidence.

## GAP-008 - Candidate Contribution Delimitation Missing

Status: open

In collaborative remote-sensing and agronomy work (multi-author satellite
products, shared codebases, multi-site ground campaigns), the candidate's
individual contribution is often unstated or vaguely co-authored. For
thesis_phd cumulative this is a hard threshold; for thesis_master it is
required for honest evaluation.

Acceptance direction: the integrity check must surface missing candidate
contribution statements as a specific finding when case_type starts with
`thesis_`. For cumulative theses, a per-paper contribution statement is
required.

## GAP-009 - Undergraduate Ghost-Writing and Fabrication Red Flags Not Audited

Status: open

For thesis_undergrad cases, the dominant failure modes are plagiarism,
ghost-writing, and data fabrication, not insufficient novelty. The system
currently has no separate artifact for these checks.

Acceptance direction: the integrity_check artifact must report training cycle
completion (problem framing / literature / data / analysis / writing),
ghost-writing red flags (style discontinuity, capability mismatch, missing
raw data, missing code version history), citation hygiene flags, and AI
disclosure status. These findings escalate to the human chair, not to
dimension scoring.
