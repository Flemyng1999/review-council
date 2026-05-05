# What Makes a Paper Good? Standards Research for review-council

Scope: journal articles and degree theses in quantitative vegetation remote
sensing, remote sensing, agriculture, and environmental physics. Medical and
humanities standards are intentionally out of scope.

## Source Base

This synthesis cross-checks five authority families:

1. Publication ethics and peer-review standards: COPE, Elsevier, Taylor &
   Francis, Springer Nature.
2. Earth science and remote-sensing journal expectations: AGU, IEEE TGRS,
   ISPRS Journal of Photogrammetry and Remote Sensing, Remote Sensing.
3. Open-science and reproducibility policies: AGU data/software policy,
   Springer Nature research data and code policy.
4. Remote-sensing validation norms: CEOS Land Product Validation, Olofsson et
   al. 2014 land-change accuracy assessment good practices.
5. Thesis examination rubrics and regulations: Wageningen University & Research
   MSc/PhD rubrics, University of Auckland doctoral thesis policy, Cambridge PhD
   thesis criteria.

## Cross-Source Consensus

A good research paper is not simply "well written" or "technically complex".
Across reviewer guidelines and thesis rubrics, quality repeatedly decomposes
into eight standards:

1. Relevance and fit: the work addresses a problem that belongs to the target
   journal, degree, or research community.
2. Contribution: the work adds something beyond competent execution. For a
   journal article this is publishable novelty or significance; for a thesis it
   may be original contribution, independent research competence, or mastery at
   the degree level.
3. Scientific validity: assumptions, design, data, methods, analysis, and
   conclusions form a defensible chain.
4. Evidence strength: claims are supported by adequate data, references,
   validation, uncertainty analysis, and comparison to alternatives.
5. Reproducibility and transparency: data, code, processing, parameters, and
   limitations are available or at least explicitly traceable.
6. Field-specific adequacy: the work meets the normal standards of its domain,
   not just generic writing standards.
7. Communication quality: the manuscript makes the research question,
   contribution, method, result, limitation, and implication understandable.
8. Integrity and review ethics: the review is fair, confidential, conflict-aware,
   constructive, and focused on the merits of the work.

## Field-Specific Standards for Remote Sensing and Environmental Physics

For vegetation quantitative remote sensing, remote sensing, agriculture, and
environmental physics, generic peer-review criteria need domain translation.

### 1. Physical and Sensor Plausibility

The paper should respect radiative-transfer, sensor, atmospheric, geometric,
and scale constraints. A remote-sensing method can be statistically strong but
physically incoherent; that is a scientific weakness, not merely a presentation
issue.

Review checks:

- Are sensor characteristics, acquisition geometry, calibration, atmospheric
  correction, BRDF/illumination effects, and spatial resolution handled or
  bounded?
- Are vegetation/soil/canopy physical mechanisms plausible?
- Are assumptions stated in a way that could fail?
- Are empirical models constrained by known physics where appropriate?

### 2. Validation Design

Remote-sensing papers often fail by treating convenient validation as decisive
validation. CEOS LPV and Olofsson et al. emphasize best-practice validation,
sampling design, reference-data quality, design-consistent analysis, uncertainty,
and documentation of deviations.

Review checks:

- Is validation independent of training/tuning?
- Is reference data spatially and temporally representative?
- Are scale mismatch and geolocation uncertainty addressed?
- Are uncertainty intervals or error propagation reported?
- Are class imbalance, stratification, and spatial autocorrelation handled?
- Are deviations from best practice documented?

### 3. Baselines, Ablations, and Transferability

A method paper needs more than high accuracy on one convenient dataset.

Review checks:

- Are baselines appropriate and current for the target problem?
- Are ablations tied to claims, not decorative?
- Is performance tested across sites, dates, sensors, crops, canopies, seasons,
  illumination conditions, or management regimes when the claim implies
  generality?
- Does the paper distinguish interpolation, extrapolation, and deployment?

### 4. Quantitative Claim Discipline

Claims must be calibrated to evidence. A paper that demonstrates a local case
study should not claim general operational readiness unless the validation
supports that leap.

Review checks:

- Does each major claim have a direct evidence anchor?
- Are limitations specific rather than generic?
- Are uncertainty and failure cases described?
- Are conclusions narrower than or equal to the evidence?

### 5. Reproducibility and Processing Traceability

AGU and Springer Nature policies make data/software availability part of the
reviewable scientific record. For remote sensing, preprocessing choices can
change the result, so traceability is central.

Review checks:

- Are data sources, versions, scenes, dates, preprocessing, masks, thresholds,
  atmospheric correction, model parameters, and software versions recorded?
- Is code available or are restrictions justified?
- Can another expert reconstruct the processing chain?

## Journal Article vs Degree Thesis

They overlap, but they are not the same object.

### Journal Article

Primary question: should this work enter the published literature of this
journal?

Dominant standards:

- fit to journal scope and readership;
- novelty, significance, or technical advance;
- soundness of method and analysis;
- adequacy of evidence for the paper's stated claims;
- concise, publishable communication;
- data/software transparency as required by the journal;
- decision support for editor: accept, revise, reject.

Failure mode: a technically competent manuscript may still be rejected if the
contribution is too incremental, the audience fit is weak, or the claims exceed
evidence.

### PhD Thesis

Primary question: does the candidate demonstrate a substantial, coherent,
original research contribution and command of the field?

Dominant standards:

- original and coherent doctoral research project;
- significant contribution to knowledge;
- command of literature and applicable research techniques;
- candidate's own contribution, especially in multi-author work;
- ability to explain what was done, why it matters, and what it changes;
- integrated introduction and general discussion, not just paper collection.

Failure mode: publishable chapters can still make a weak thesis if the
candidate's intellectual ownership, coherence, literature command, or general
discussion is weak.

### Master's Thesis

Primary question: does the student demonstrate independent research competence
at master's level?

Dominant standards:

- clear research question;
- appropriate design and execution;
- correct use of methods;
- ability to interpret results and limitations;
- adequate engagement with literature;
- written report quality and often oral defense/presentation quality.

Failure mode: the work may not need to be highly novel, but it must show
independent, disciplined, technically correct research.

### Bachelor's Thesis

Primary question: does the student demonstrate undergraduate-level research
literacy, technical competence, and clear reporting?

Dominant standards:

- correct understanding of the problem;
- appropriate basic method;
- careful execution;
- honest limitation;
- clear writing and citation practice.

Failure mode: novelty should not be over-weighted. The main concern is whether
the student can conduct and report a bounded piece of research responsibly.

## Granularity Principle

A high-level review and a line-by-line review reveal different failures. The
review system should preserve both.

Macro review asks:

- What is the paper trying to contribute?
- Is the contribution worth doing?
- Is the system complete enough?
- Is the scientific story coherent?
- Are the claims proportional to the evidence?

Local review asks:

- Does this section do its job?
- Does this equation follow?
- Is this dataset adequate for this claim?
- Is this figure interpretable and honest?
- Is this citation the right source?
- Is this limitation real or cosmetic?

The reviewer must not substitute one for the other. A paper can be locally
polished but globally unimportant; it can also have a strong idea but fail in
methodological detail.

## AI-Assisted Review Implications

AI should be used as an accelerator for reading, extraction, comparison,
verification, dissent, and synthesis. It should not own judgment.

Useful AI roles:

- structure extractor: sections, claims, figures, tables, methods, datasets;
- evidence clerk: claim-to-evidence matrix and missing anchors;
- domain reviewer: physical plausibility and field norms;
- methods/statistics reviewer: validation, baselines, uncertainty;
- dissent reviewer: strongest argument against the emerging consensus;
- synthesis writer: decision-ready summary that preserves unresolved
  disagreements.

Human-owned responsibilities:

- decide review target and threshold;
- decide whether a claim matters;
- decide whether evidence is sufficient;
- decide final judgment;
- ensure the review is fair, useful, and proportionate.

## Source Trail

- COPE Ethical Guidelines for Peer Reviewers:
  https://members.publicationethics.org/sites/default/files/cope-ethical-guidelines-peer-reviewers-v2_0.pdf
- Elsevier reviewer guide:
  https://www.elsevier.com/reviewer/how-to-review
- Elsevier reviewer checklist:
  https://www.elsevier.com/en-gb/reviewer/how-to-review/checklist
- Taylor & Francis peer review process:
  https://editorresources.taylorandfrancis.com/reviewer-guidelines/peer-review-process/
- Taylor & Francis review checklist:
  https://editorresources.taylorandfrancis.com/reviewer-guidelines/review-checklist/
- Springer Nature peer review guide:
  https://www.springernature.com/gp/authors/campaigns/how-to-peer-review-2
- AGU review criteria:
  https://www.agu.org/Publications/Reviewers/Review-Criteria
- AGU data/software guidance:
  https://www.agu.org/publish-with-agu/publish/author-resources/data-and-software-for-authors
- AGU data/software checklist:
  https://data.agu.org/resources/availability-citation-checklist-for-authors
- Springer Nature research data policy:
  https://www.springernature.com/gp/authors/research-data-policy
- Springer Nature data availability policy:
  https://www.springer.com/in/editorial-policies/data-availability-statement
- Springer Nature code sharing:
  https://support.springer.com/en/support/solutions/articles/6000237619-software-and-code-sharing
- IEEE TGRS information for authors:
  https://www.grss-ieee.org/publications/author-resources/tgrs-information-for-authors/
- ISPRS Journal guide for authors:
  https://www.sciencedirect.com/journal/isprs-journal-of-photogrammetry-and-remote-sensing/publish/guide-for-authors
- Remote Sensing aims and scope:
  https://www.mdpi.com/journal/remotesensing/about
- Remote Sensing instructions for authors:
  https://www.mdpi.com/journal/remotesensing/instructions
- CEOS Land Product Validation:
  https://ceos.org/ourwork/workinggroups/wgcv/subgroups/lpv/
- CEOS LPV documents:
  https://lpvs.gsfc.nasa.gov/documents.html
- Olofsson et al. 2014 good practices summary:
  https://nottingham-repository.worktribe.com/output/728216/good-practices-for-estimating-area-and-assessing-accuracy-of-land-change
- Olofsson et al. 2014 DOI page:
  https://www.sciencedirect.com/science/article/pii/S0034425714000704
- Wageningen MSc thesis rubric:
  https://zenodo.org/records/10528242
- Wageningen MSc thesis course guide:
  https://www.wur.nl/nl/show/guide-for-thesis-students-esa.htm
- Wageningen PhD thesis evaluation form:
  https://www.wur.nl/nl/show/phd-thesis-evaluation-form.htm
- University of Auckland doctoral thesis policy:
  https://www.auckland.ac.nz/en/about-us/about-the-university/policy-hub/research-innovation/doctoral-study/undertaking-research/doctoral-thesis-policy-procedures.html
- Cambridge PhD thesis criteria example:
  https://www.hps.cam.ac.uk/students/phd-guide/thesis
