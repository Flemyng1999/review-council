---
name: methodology
dimension: methodology
description: Whether the design — physical and statistical — supports what is claimed.
applicable_layers: [chapter, section]
applicable_case_types: [journal, thesis_undergrad, thesis_master, thesis_phd]
checks:
- id: MET-01
  text: Forward radiative-transfer model choice (PROSPECT, SAIL, 4SAIL, DART, LESS, SCOPE, etc.) is justified for canopy structure, bands, and viewing geometry.
  severity_if_failed: major
- id: MET-02
  text: Atmospheric correction, BRDF, and topographic correction are transparent and consistent with downstream inversion assumptions.
  severity_if_failed: major
- id: MET-03
  text: Inversion ill-posedness, equifinality, and saturation are explicitly discussed when applicable; priors and regularization are stated.
  severity_if_failed: major
- id: MET-04
  text: Train / validation / test splits avoid spatial and temporal autocorrelation leakage; block-based or site-based CV is used when locations or seasons overlap.
  severity_if_failed: major
- id: MET-05
  text: Cross-site, cross-year, or cross-sensor transferability is reported when generality is claimed; performance is not only same-distribution holdout.
  severity_if_failed: major
- id: MET-06
  text: Multiple metrics are reported (RMSE, bias, R^2, ubRMSE, MAPE, KGE) appropriate to the task; not a single metric.
  severity_if_failed: moderate
- id: MET-07
  text: Ablations and baselines are tied to the paper's specific claims, not decorative.
  severity_if_failed: moderate
- id: MET-08
  text: Sample size, class imbalance, and rare regimes (extremes, uncommon phenology) are handled or acknowledged.
  severity_if_failed: moderate
- id: MET-09
  text: Physical consistency checks exist where applicable — energy or mass balance, albedo bounds, LAI / fAPAR relationships, NDVI saturation thresholds.
  severity_if_failed: moderate
---

# Methodology

Sources: NIH Factor 2 (Rigor and Feasibility), NeurIPS / ICML soundness
criteria, CEOS LPV protocols, RSE technical expectations.

Two axes are checked together: physical / forward modeling and
statistical / learning. A method can be statistically strong but physically
incoherent; both must hold.

Spatial and temporal data leakage is the single most common silent failure
in remote sensing and agronomy ML papers — block-based or site-based CV is
treated as a hard expectation when sites or seasons overlap.
