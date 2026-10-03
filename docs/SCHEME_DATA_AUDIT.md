# Scheme data audit – 29 Sep 2026 (Update 3)

## Why a PG student saw “AICTE Swanath – Degree / Diploma”
The bot filters schemes on the file `data/scheme_rules_v3.json`, which is built from the master Excel by
`python tools/compile_master.py`. The education-level fix on GitHub (commit f1cf76d) changed the code that
builds this file, but the file itself was **not rebuilt**, so the live bot still used the old one. In that
old file most schemes had no education level at all, only the broad stage (“Post-Matric” / “Higher
Education”). A PG answer counts as both, so PG students also got Degree-only and Diploma-only schemes.
The synthetic master made this worse: its “Education Level / Stage” column often contradicts the scheme name
(for example “Class 11 to UG” for a fellowship, “ITI” for a medical course).

## What was checked
All **525 active schemes** (547 rows; 22 superseded rows are ignored), comparing the scheme **name** with
the fields the bot filters on:

| Check | Mismatches before (live) | After |
|---|---|---|
| Education level (name says Pre-Matric / Class 11-12 / Diploma / ITI / Degree / UG / PG / PhD / Fellowship … but the bot showed it to other levels, or no level could see it) | 109 | 0 |
| Social category (name says SC / ST / OBC / EBC / DNT / Minority … but the data says something else) | 23 | 0 |
| Gender (name says girls / boys / both, data disagrees) | 1 | 0 |
| State (name mentions a different State than the scheme's State) | 0 | 0 |
| Income (missing / unreadable / impossible values) | 0 | 0 |

Profile test: 600 student profiles (5 levels × 6 States × 2 genders × 5 categories × 2 income bands).
Before: 15,210 results, of which 5,676 contradicted the scheme name on education and 64 on category.
After: 7,752 results, 0 contradictions. (Most of the drop comes from education levels that are now applied
at all; each level now sees only the schemes meant for it.)

**Karnataka, PG, Male, General, ₹10,001–30,000 a month:** before 21 schemes (1. AICTE Swanath – Degree,
2. AICTE Swanath – Diploma, 3. ICAR JRF/SRF, 4. ICAR NTS-PG, 5. ICAR NTS-UG). After 12 schemes
(1. ICAR JRF/SRF, 2. ICAR NTS-PG, 3. ICAR Post Graduate Scholarship, 4. Junior Research Fellowship in
Science, Humanities and Social Sciences, 5. National Renewable Energy Fellowship).

## How it is fixed (the master Excel is not changed)
Everything is done in `app/eligibility/overlay.py` when the rules file is built, and every change is written
to the scheme's `Overlay_Notes` and to `docs/scheme_data_audit_changes.xlsx`.

1. **Education level.** Order of trust: a clear signal in the scheme name (Pre-Matric, Class IX-XII,
   Std 11-12, Passed Class 10 / 12, Intermediate passed, Diploma / Polytechnic, Degree, UG, Postgraduate,
   M.Phil / PhD, Research, Fellowship, Medical / Engineering …) → a broad band in the name (Post-Matric,
   school, college / university) combined with the master's level → the master's level on its own. The
   original “Education Stage (Rule 6)” column (derived from the name before the synthetic fill) is used as a
   cross-check: a synthetic level that contradicts it is dropped. Before, 10 schemes could not be seen by any
   student (e.g. NMMSS, Kali Bai Bheel Scooty – Passed Class 12, Sainik School Ghorakhal); now every active
   scheme is reachable.
2. **Social category.** If the scheme name names categories and the master names different ones, the name
   wins. Mostly EBC schemes that the synthetic master marked “OBC” (EBC = economically backward, i.e.
   General), and “OBC, EBC and DNT” schemes that now include General (EBC) students. Exceptions written in:
   Bihar BC/EBC = OBC lists only; “Open category students affected by SEBC/EWS reservation” = General;
   “Adi Dravidar” = SC.
3. **Gender.** “Mukhyamantri Balak/Balika Protsahan Yojana” is for boys and girls (the master said Female).
4. The rules file was **rebuilt**, and card texts stay within 80 / 80 / 90 characters (description /
   eligibility / documents).

`docs/CATEGORY_AUDIT.md` (Update 1) describes the earlier verified master and was not regenerated.

Re-run the audit any time: `python tools/scheme_data_audit.py --xlsx audit.xlsx`.

## For Rajat to decide / confirm
* Diploma, polytechnic and ITI courses count as “Class 12 passed” (as the chat's answer label says). A
  diploma student who joined after Class 10 must choose “Class 12 passed” to see them.
* The synthetic master restricts many schemes whose names say nothing about category, gender or level
  (e.g. PM-USP “College and University Students” marked “Class 11 to UG”, so PG students do not see it).
  These are not contradictions, so they were left as the synthetic data says.
* EBC is treated as General (economically backward), except in Bihar where EBC is an OBC list.
* This is synthetic test data; official verification is still needed before production.
