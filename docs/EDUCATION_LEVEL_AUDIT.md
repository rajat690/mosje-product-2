# Product 2 education-level audit — 29 Sep 2026

> **Update 3 (29 Sep 2026, later):** this fix was on GitHub but `data/scheme_rules_v3.json` had not been rebuilt, so the live bot did not use it. The rules are now rebuilt and the audit extended to the whole database (category, gender, State, income too). See `docs/SCHEME_DATA_AUDIT.md`; the Karnataka PG example now returns 12 schemes (UG+PG schemes such as the ISI stipend are kept for PG).

## Defect found
The discovery engine first checked broad scholarship stages (`Pre-Matric`, `Post-Matric`, `Higher Education`).
A PG answer is represented as both `Post-Matric` and `Higher Education`, so a PG student could pass schemes that were actually Degree/UG-only or Diploma-only. The finer `Education Level / Stage` value existed in the scheme data but most of its synthetic labels were not converted into `Level_Codes`.

Example: AICTE Swanath Degree had `Higher Education` + `Class 11 to UG`; Swanath Diploma had `Post-Matric` + `Diploma/Polytechnic`. Both therefore appeared for PG before this fix.

## Fix
1. `overlay.py` now converts controlled education labels into the chatbot's current-level codes: PRE, X, XII, UG, PG.
2. Strong, unambiguous scheme-name signals override contradictory synthetic education labels for Diploma, AICTE Degree variants, Pre-Matric, PG, UG, research/fellowship, and PM scholarship variants.
3. `engine.py` enforces `Level_Codes` before the broader stage check, including schemes whose broad Education Stage is blank/not specified.
4. Added regression tests for PG vs Swanath Degree/Diploma, Saksham Degree/Diploma, NTS-UG, and positive PG/research matches.

## Audit result
- Total compiled rows: 547
- Active rows: 525
- Excluded superseded/aggregate rows: 22
- Active rows with a finer current-education constraint after fix: 368
- Active rows left broad/unconstrained: 157. These are intentionally broad or use ambiguous labels such as `Higher Education`, `School`, `Education`, or mixed programme families.
- Obvious title-level signals (Pre-Matric, Postgraduate, Diploma/Polytechnic, Fellowship/Research, NTS-UG/PG, explicit Degree variants) left unconstrained: 0.

## Regression scenario
For Karnataka + PG + Male + General + annual income ₹3.6 lakh, the result set fell from 21 to 10. Removed false positives include AICTE Swanath Degree, AICTE Swanath Diploma, AICTE Saksham Degree/Diploma, ICAR NTS-UG, and the UG-only Prime Minister scholarship variants.

The master is synthetic/test data. This audit improves internal consistency; it is not a substitute for scheme-by-scheme official verification before production use.
