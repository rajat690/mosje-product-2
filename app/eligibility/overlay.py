"""Product 2 discovery overlay on top of the V3.0 scheme master.

WHY. The master leaves the social-category column as "Not specified in verified source" for about
300 schemes. Under Eligibility Rule V3.0 "not specified" means the check PASSES, so a General
student was shown schemes whose NAME says they are for Backward Classes / SC / OBC / minorities
(feedback 1, 29 Sep 2026). For a student-facing discovery assistant that is wrong and erodes trust.

WHAT. When the master does not restrict a condition, restrictions are inferred from the scheme
name (and, for category only, from a single-purpose department name). Every inference is recorded
in Category_Source / Gender_Source / Overlay_Notes and listed in docs/CATEGORY_AUDIT.md for review.
  * Social category  : SC, ST, OBC (incl. BC/MBC/SEBC/SBC/VJNT/DNT/NT/DNC/OEC/Kapu/Developing Castes),
                       General (EBC / EWS / economically backward), Minority.
  * Gender           : girls / women / kanya ... -> Female; boys -> Male.
  * Target groups    : disability (asked in the chat), farmer family, specific workers' children,
                       armed forces/police/freedom-fighter families, specific schools/cadets,
                       orphans/child care/widows, BPL families, teachers' children, other.
                       Non-disability groups are not asked; such schemes are shown last, marked
                       "Only for ... - check eligibility".
  * Region           : Central schemes limited to a region (North East, J&K + Ladakh).
Master values that already restrict a condition are never loosened. If the master says
"all categories" but the name clearly names a category, the name wins and the row is flagged
'master+name-conflict'.

This overlay is a Product 2 discovery refinement. It is NOT part of Eligibility Rule V3.0 and
does not change Product 1's eligibility engine.
"""
from __future__ import annotations

import re
from dataclasses import replace

from .rules_compiler import CATEGORIES, NO_REQ, PARSED, SchemeRule

NE_STATES = ("Arunachal Pradesh", "Assam", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Sikkim", "Tripura")

# ------------------------------------------------------------------ curated names (checked first)
# (case-insensitive substring of scheme name) -> overrides. Documented in the audit report.
CURATED = [
    ("free coaching for scs, obcs", {"categories": {"SC", "OBC"}, "groups": set(),
                                     "note": "SC/OBC students (PM CARES children also eligible)"}),
    ("home nursing scholarship", {"groups": set(), "note": "master already limits to SC/OBC/Minority (disabled also listed)"}),
    ("widow/divorcee", {"gender": "Female", "note": "for widowed/divorced women"}),
    ("tea tribes", {"categories": {"OBC", "ST"}, "note": "Assam tea tribes/Adivasi (OBC/ST)"}),
    ("aikyashree", {"categories": {"Minority"}, "note": "West Bengal minority scholarship"}),
    ("muhammed koya", {"categories": {"Minority"}, "gender": "Female", "note": "Kerala minority girls"}),
    ("ayyankali", {"categories": {"SC", "ST"}, "note": "Kerala SC/ST talent scheme"}),
    ("thakur sen negi", {"categories": {"ST"}, "note": "Himachal ST merit scheme"}),
    ("sahariya", {"categories": {"ST"}, "note": "Sahariya tribe (ST)"}),
    ("aicte pragati", {"gender": "Female", "note": "AICTE Pragati is for girl students"}),
    ("aicte saksham", {"groups": {"disability"}, "note": "AICTE Saksham is for specially-abled students"}),
    ("kali bai bheel", {"gender": "Female", "note": "Scooty scheme for girl students"}),
    ("kishori", {"gender": "Female"}),
    ("pudhumai penn", {"gender": "Female", "note": "Tamil Nadu scheme for girls"}),
    ("tamil pudhalvan", {"gender": "Male", "note": "Tamil Nadu scheme for boys"}),
    ("nijut moina", {"gender": "Female", "note": "Assam scheme for girls"}),
    ("nijut babu", {"gender": "Male", "note": "Assam scheme for boys"}),
    ("kalpana chawla", {"gender": "Female", "note": "Himachal scheme for girls"}),
    ("single girl child", {"gender": "Female", "groups": {"other"}, "note": "only-child girls"}),
    ("north eastern region", {"region": NE_STATES}),
    ("nec merit", {"region": NE_STATES}),
    ("jammu & kashmir and ladakh", {"region": ("Jammu and Kashmir", "Ladakh")}),
]

# ------------------------------------------------------------------ category keywords
# Case-SENSITIVE short tokens (so 'SC' does not match 'SSC', 'ST' not 'Std').
TOKENS = [
    (r"\bEBCs?\b|\bEWS\b", {"General"}, "EBC/EWS"),
    (r"\bOBCs?\b|\bBCs?\b|\bMBCs?\b|\bSEBCs?\b|\bSBCs?\b|\bVJNT\b|\bDNTs?\b|\bDNCs?\b|\bNT\b|\bOEC\b", {"OBC"},
     "OBC/BC/MBC/SEBC/SBC/VJNT/DNT/DNC/OEC"),
    (r"\bSCs?\b", {"SC"}, "SC"),
    (r"\bSTs?\b|\bAPST\b", {"ST"}, "ST"),
]
# Case-insensitive phrases; each matched phrase is removed before later rules run.
PHRASES = [
    (r"(other\s+)?economically\s+(backward|weaker)(\s+class(es)?|\s+section(s)?)?", {"General"}, "economically backward/weaker"),
    (r"brahmin", {"General"}, "Brahmin"),
    (r"scheduled\s+castes?|annu?s[ua]chit\s+jati|dalit", {"SC"}, "Scheduled Caste"),
    (r"(nomadic|de-?notified)([\s/&,-]+(and\s+)?(nomadic|de-?notified))*[\s/&,-]*(tribes?)?|most\s+backward|other\s+backward|backward\s+class(es)?|developing\s+castes|\bkapu\b",
     {"OBC"}, "Backward Class / DNT / Nomadic / Kapu / Developing Castes"),
    (r"scheduled\s+tribes?|\btribal\b|\btribes?\b|adivasi", {"ST"}, "Scheduled Tribe / tribal"),
    (r"minorit(y|ies)|alpasankhyak|muslim|christian|maulana\s+azad|begum\s+hazrat|madrasa", {"Minority"}, "Minority"),
]
# Single-purpose departments (used only if the name gives nothing).
DEPARTMENTS = [
    (r"^director,\s*scheduled caste welfare$|^scheduled castes? development$", {"SC"}),
    (r"^adi dravidar & tribal welfare$|^sc/st (development departments|welfare)$", {"SC", "ST"}),
    (r"^director,\s*developing castes welfare$|^backward classes (welfare|development)( department)?$|"
     r"^obc, sebc, vjnt & sbc welfare department$", {"OBC"}),
    (r"^backward classes welfare / tribal development$", {"OBC", "ST"}),
    (r"^backward classes & minorities welfare$", {"OBC", "Minority"}),
    (r"^tea tribes & adivasi welfare department$", {"OBC", "ST"}),
    (r"^(tribal (development|welfare)( department)?|scheduled tribes development department|"
     r"directorate of tribal welfare|tribal affairs)$", {"ST"}),
    (r"^(minority (welfare|development)( department)?.*|directorate of minorities|minorities welfare|"
     r"minority affairs and madrasah education.*)$", {"Minority"}),
]
DISABILITY_DEPTS = re.compile(r"persons with disabilities|differently abled", re.I)

# ------------------------------------------------------------------ gender keywords
FEMALE = re.compile(r"\bgirls?'?\b|\bwomen\b|\bfemale\b|\bkanya\b|\bbeti\b|\bmahila\b|\bbalika\b", re.I)
MALE = re.compile(r"\bboys?\b|\bbalak\b", re.I)

# ------------------------------------------------------------------ target groups
GROUPS = [
    ("defence", re.compile(r"ex-?servicem[ae]n|armed forces|\bcapf\b|assam rifles|police personnel|"
                           r"service personnel|martyr|freedom fighters?|ministry of railways", re.I)),
    ("disability", re.compile(r"disabilit|\bdisabled\b|differently\s+abled|divyang|handicap|\bblind\b|"
                              r"special needs|specially\s+abled|\bpwd\b|persons with disability", re.I)),
    ("farmer", re.compile(r"farmer", re.I)),
    ("workers", re.compile(r"beedi|construction workers?|unclean occupation|cleaning|hazardous occupation|"
                           r"health-hazard", re.I)),
    ("school", re.compile(r"sainik|\brimc\b|military college|government school|govt\.? school|"
                          r"government/aided school|vidyaniketan|\bncc\b|\bnda\b|7\.5% reservation", re.I)),
    ("orphan", re.compile(r"pm cares|orphan|mission vatsalya|child care|widow|divorcee", re.I)),
    ("bpl", re.compile(r"\bBPL\b")),
    ("teachers", re.compile(r"children of school teachers", re.I)),
    ("other", re.compile(r"bengali-origin|national child award|border area", re.I)),
]


def infer_categories(name: str) -> tuple[set, list]:
    found, why = set(), []
    for pat, cats, label in TOKENS:
        if re.search(pat, name):
            found |= cats
            why.append(label)
    text = name
    for pat, cats, label in PHRASES:
        if re.search(pat, text, re.I):
            found |= cats
            why.append(label)
            text = re.sub(pat, " ", text, flags=re.I)
    return found, why


def infer_department(dept: str) -> set:
    d = (dept or "").strip().lower()
    for pat, cats in DEPARTMENTS:
        if re.search(pat, d):
            return set(cats)
    return set()


def infer_gender(name: str) -> str | None:
    f, m = bool(FEMALE.search(name)), bool(MALE.search(name))
    if f and not m:
        return "Female"
    if m and not f:
        return "Male"
    return None


def infer_groups(name: str, dept: str) -> set:
    out = set()
    for key, rx in GROUPS:
        if rx.search(name):
            out.add(key)
    if "defence" in out:                     # 'Killed/Disabled in War' is about the parent, not the student
        out.discard("disability")
    if DISABILITY_DEPTS.search(dept or ""):
        out.add("disability")
    return out


# Education levels asked by the bot (answers.class_passed): PRE = studying Class 1-10 (Pre-Matric),
# X = Class 10 passed, XII = Class 12 passed, UG = studying for a degree, PG = master's / research.
LEVELS = ["PRE", "X", "XII", "UG", "PG"]

# Product 2 asks for CURRENT education level, not merely whether a scheme is broadly
# "Post-Matric" or "Higher Education".  These controlled mappings prevent a PG student
# from receiving UG/diploma-only schemes (and vice versa).
LEVEL_MAP = {
    "class 1–10": {"PRE"}, "class 1-10": {"PRE"}, "class 9–10": {"PRE"}, "class 9-10": {"PRE"},
    "class 11–12": {"X"}, "class 11-12": {"X"},
    "class 11 to ug": {"X", "XII", "UG"},
    "class 11 to pg": {"X", "XII", "UG", "PG"},
    "diploma/polytechnic": {"XII"}, "diploma / polytechnic": {"XII"}, "iti": {"XII"},
    "ug": {"UG"}, "undergraduate": {"UG"}, "undergraduate first year": {"UG"},
    "pg": {"PG"}, "postgraduate": {"PG"}, "post graduation": {"PG"},
    "phd/research": {"PG"}, "phd / research": {"PG"}, "m.phil / phd": {"PG"},
    "phd": {"PG"}, "research": {"PG"}, "postdoctoral research": {"PG"},
    "ug/pg professional or technical course": {"UG", "PG"},
    "undergraduate / technical": {"UG"}, "undergraduate / professional": {"UG"},
    "higher education / research": {"PG"}, "research / higher education": {"PG"},
    "sslc / puc / degree": {"PRE", "X", "UG"},
    "masters / higher education": {"PG"}, "post-graduation completion": {"PG"},
    "graduate": {"UG"}, "graduate women": {"UG"}, "m.sc. agriculture": {"PG"},
}

def infer_level_codes(name: str, raw: str) -> tuple[set, str]:
    """Return controlled current-education codes plus an audit source.

    Strong scheme-name signals override a contradictory synthetic Education Level field.
    This is intentionally conservative: only labels that clearly identify a level are used.
    """
    n = (name or "").lower()
    r = (raw or "").strip().lower()

    # Explicit split variants are the strongest signal.
    if "diploma" in n or "polytechnic" in n:
        return {"XII"}, "scheme-name:diploma"
    if re.search(r"\bdegree\b", n) and any(x in n for x in ("aicte", "swanath", "saksham", "pragati")):
        return {"UG"}, "scheme-name:degree"
    if "pre-matric" in n or "pre matric" in n:
        return {"PRE"}, "scheme-name:pre-matric"
    if re.search(r"post[ -]?graduate|\bpgs?\b|nts-pg", n):
        return {"PG"}, "scheme-name:postgraduate"
    if re.search(r"nts-ug|\bundergraduate\b|\bug scholarship\b", n):
        return {"UG"}, "scheme-name:undergraduate"
    if any(x in n for x in ("junior research fellowship", "senior research fellowship", "postdoctoral",
                            "research fellowship", "research scholarship")):
        return {"PG"}, "scheme-name:research"
    if "fellowship" in n and not any(x in n for x in ("school", "pre-matric")):
        return {"PG"}, "scheme-name:fellowship"
    if "prime minister's scholarship scheme" in n or "prime ministers scholarship scheme" in n:
        return {"UG"}, "scheme-name:PM scholarship"

    lv = LEVEL_MAP.get(r)
    if lv:
        return set(lv), "master-education-level"
    return set(), ""


def apply_overlay(r: SchemeRule) -> SchemeRule:
    name = r.Scheme_Name
    low = name.lower()
    cur = next((v for k, v in CURATED if k in low), None)
    notes = []
    upd = {}

    # ---- social category
    master_restricts = r.Category_Status != NO_REQ
    master_explicit_all = master_restricts is False and not r.Category_Raw.lower().startswith("not specified") \
        and r.Category_Raw != ""
    cats, why = (set(cur["categories"]), ["curated: " + cur.get("note", "")]) if cur and "categories" in cur \
        else infer_categories(name)
    source = None
    if cats and not master_restricts:
        source = "master+name-conflict" if master_explicit_all else "inferred-name"
    elif not cats and not master_restricts and not master_explicit_all \
            and not infer_groups(name, r.Department):   # occupation/school schemes are open to all castes
        dcats = infer_department(r.Department)
        if dcats:
            cats, why, source = dcats, [f"department '{r.Department}'"], "inferred-department"
    if source:
        label = "; ".join(c for c in CATEGORIES if c in cats)
        upd.update(category_set=frozenset(cats), Category_Status=PARSED, Categories_Allowed=label,
                   Category_Source=source,
                   Category_Note=(r.Category_Note + " | " if r.Category_Note else "") +
                   f"P2 overlay: {label} ({', '.join(why)})")
        notes.append(f"category {label} [{source}: {', '.join(why)}]")

    # ---- gender
    if r.Gender_Status == NO_REQ:
        g = cur.get("gender") if cur and "gender" in cur else infer_gender(name)
        if g:
            upd.update(gender_set=frozenset({g}), Gender_Status=PARSED, Gender_Allowed=g, Gender_Source="inferred-name")
            notes.append(f"gender {g} [name]")

    # ---- target groups
    groups = set(cur["groups"]) if cur and "groups" in cur else infer_groups(name, r.Department)
    if "disability" not in groups and "disabilit" in (r.Category_Raw or "").lower():
        groups.add("disability")             # e.g. 'All categories; disability ...'
    if groups:
        upd["Target_Groups"] = "; ".join(sorted(groups))
        notes.append(f"only for: {', '.join(sorted(groups))}")

    # ---- region (Central schemes limited to some States/UTs)
    if cur and "region" in cur and r.Scheme_Level == "Central":
        upd["Region_States"] = "; ".join(cur["region"])
        notes.append(f"region: {upd['Region_States']}")

    # ---- education level (finer than the Rule 6 stage, only where the master is specific)
    lv, lv_source = infer_level_codes(name, r.Education_Level_Raw)
    if lv:
        upd["Level_Codes"] = "; ".join(x for x in LEVELS if x in lv)
        notes.append(f"education level: {upd['Level_Codes']} [{lv_source}; raw='{r.Education_Level_Raw}']")

    if not upd:
        return r
    upd["Overlay_Notes"] = " | ".join(notes)
    return replace(r, **upd)
