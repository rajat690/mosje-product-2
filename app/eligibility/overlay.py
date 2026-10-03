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

from .rules_compiler import CATEGORIES, NO_REQ, PARSED, STAGES, SchemeRule

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
    ("bc/ebc students - bihar", {"categories": {"OBC"}, "note": "Bihar BC/EBC = Backward / Extremely Backward Classes (both OBC lists)"}),
    ("open category students affected by", {"categories": {"General"}, "note": "for open-category (General) students"}),
    ("balak/balika", {"gender": "All", "note": "for boys and girls (balak/balika)"}),
    ("kanyashree", {"gender": "Female", "note": "West Bengal scheme for girls"}),
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
    (r"scheduled\s+castes?|annu?s[ua]chit\s+jati|dalit|adi\s+dravidar", {"SC"}, "Scheduled Caste / Adi Dravidar"),
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

ALL_LEVELS = frozenset(LEVELS)
POST = frozenset({"X", "XII", "UG", "PG"})
COLLEGE = frozenset({"XII", "UG", "PG"})
# Levels whose derived Rule-6 stage (engine.derive_education_stage) meets each broad stage.
STAGE_LEVELS = {"Pre-Matric": {"PRE"}, "Post-Matric": {"X", "XII", "UG", "PG"}, "Higher Education": {"XII", "UG", "PG"}}
LEVEL_STAGES = {"PRE": {"Pre-Matric"}, "X": {"Post-Matric"}, "XII": {"Post-Matric", "Higher Education"},
                "UG": {"Post-Matric", "Higher Education"}, "PG": {"Post-Matric", "Higher Education"}}

# Curated education levels for names whose wording would otherwise be misread (checked first).
LEVEL_CURATED = [
    ("fellowship and scholarship for higher education of st students - scholarship", {"UG", "PG"},
     "NFST scholarship component (top-class degree/PG study), not the fellowship"),
    ("other than intermediate", {"XII", "UG", "PG"}, "UP post-matric for courses other than Class 11-12"),
    ("sslc/puc/degree", {"X", "XII", "UG"}, "incentive after passing SSLC / PUC / degree"),
]

# STRONG name signals: an explicit class, course or degree in the scheme name. They replace a
# contradictory synthetic 'Education Level / Stage' value. Evaluated in order; first match wins.
LEVEL_STRONG = [
    (r"pre[- ]?(matric|ssc)\b.*post[- ]?(matric|ssc)|pre\s*/\s*post[- ]?matric", ALL_LEVELS, "pre- and post-matric"),
    (r"undergraduate and postgraduate|graduate and postgraduate|\bug\s*(/|and|&)\s*pg\b", {"UG", "PG"}, "UG and PG"),
    (r"\bb\.sc\.?.*\bm\.sc\b", {"UG", "PG"}, "B.Sc. and M.Sc."),
    (r"degree\s*/\s*diploma|diploma\s*/\s*degree", {"XII", "UG"}, "degree or diploma"),
    (r"medical,\s*engineering and diploma", {"XII", "UG", "PG"}, "medical, engineering and diploma"),
    (r"pre[- ]?(matric|ssc)", {"PRE"}, "pre-matric"),
    (r"diploma|polytechnic|\biti\b.*trainee|\biti trainees\b|craftsman training", {"XII"}, "diploma / polytechnic / ITI"),
    (r"class i-viii and iti", {"PRE", "XII"}, "Class I-VIII and ITI"),
    (r"master degree|master'?s degree|post[ -]?graduat|\bp\.?g\.?\s+research|\bpgs?\b|nts-pg|m\.phil|ph\.?\s?d|"
     r"doctoral|thesis|m\.sc\.? agriculture", {"PG"}, "postgraduate / M.Phil / PhD"),
    (r"junior research fellowship|senior research fellowship|research fellowship|research scholarship|"
     r"postdoctoral|\bresearch\b", {"PG"}, "research"),
    (r"\bfellowship\b", {"PG"}, "fellowship"),
    (r"medical|dental|engineering|mbbs", {"UG", "PG"}, "medical / dental / engineering course"),
    (r"\bdegree\b|nts-ug|\bundergraduate\b|\bug\b|graduation incentive", {"UG"}, "degree / undergraduate"),
    (r"prime minister'?s scholarship scheme", {"UG"}, "PM scholarship (professional degree)"),
    (r"first year girls", {"XII", "UG"}, "first-year college"),
    (r"intermediate passed|passed class 12|class 12 passed|post plus two|10\+2 passed", {"XII", "UG"}, "Class 12 passed"),
    (r"class x (&|and) xii passed|std\.? ?(10|x) and (12|xii)|sslc/ssc/intermediate", {"X", "XII"}, "Class 10 / Class 12 exam"),
    (r"matric passed|passed class 10", {"X"}, "Class 10 passed"),
    (r"\b(class(es)?|std\.?)\s*(i|1|iii|v|vi)\s*(-|to)\s*(xii|12)\b|\b(vi|ix)-xii\b|\(i-xii\)", {"PRE", "X"}, "Class up to XII"),
    (r"\b(xi|11)\s*-\s*(xii|12)\b|higher secondary|10\+2 education|junior college|\bhsslc\b|intermediate scholarship|"
     r"std\.? ?12\b|class 12 students", {"X"}, "Class 11-12"),
    (r"\b(class(es)?|std\.?)?\s*(i|iii|v|vi|ix)\s*-\s*(vi|viii|x)\b|\bstd\.? ?(9|ix)\b|primary|middle stage|madhyamik",
     {"PRE"}, "Class 1-10"),
]
# RANGE name signals: a broad band. Intersected with the synthetic level when they overlap.
LEVEL_RANGE = [
    (r"post[- ]?(matric|ssc)|after secondary", POST, "post-matric"),
    (r"sainik school|military college|\brimc\b|\bschools?\b(?! teachers)", {"PRE", "X"}, "school"),
    (r"college|university|higher (education|studies)|uchch?a? shiksha|ucch shiksha|professional course", COLLEGE,
     "college / higher education"),
]


def _match(rules, n):
    for pat, lv, label in rules:
        if re.search(pat, n):
            return set(lv), label
    return None, ""


def infer_level_codes(name: str, raw: str) -> tuple[set, str]:
    """Current-education codes before the Rule-6 stage consistency step (kept for callers/tests)."""
    codes, _stage, source = resolve_education(name, raw, "Not specified", frozenset())
    return codes, source


def resolve_education(name: str, raw: str, stage_status: str, stage_set) -> tuple[set, set | None, str]:
    """Return (level codes, stage override or None, audit source).

    Order of trust: curated name > strong scheme-name signal > broad name band intersected with the
    synthetic 'Education Level / Stage' > synthetic value alone. The original 'Education Stage (Rule 6)'
    (derived from name/notes before the synthetic fill) is used as a consistency check: a synthetic
    level that contradicts it is dropped; a name signal that contradicts it replaces the stage.
    """
    n = (name or "").lower()
    r = (raw or "").strip().lower()
    synth = set(LEVEL_MAP.get(r, set()))
    allowed = set(ALL_LEVELS)
    if stage_status == PARSED and stage_set:
        allowed = set().union(*(STAGE_LEVELS[x] for x in stage_set if x in STAGE_LEVELS))

    kind, codes, label = "", set(), ""
    for key, lv, note in LEVEL_CURATED:
        if key in n:
            kind, codes, label = "curated", set(lv), f"curated: {note}"
            break
    if not kind:
        lv, lab = _match(LEVEL_STRONG, n)
        if lv:
            kind, codes, label = "strong", lv, f"scheme-name: {lab}"
    if not kind:
        lv, lab = _match(LEVEL_RANGE, n)
        if lv:
            both = lv & synth
            kind = "range"
            if both:
                codes, label = both, f"scheme-name band '{lab}' ∩ master level"
            elif synth:
                codes, label = lv, f"scheme-name band '{lab}' (master level '{raw}' contradicts it)"
            else:
                codes, label = lv, f"scheme-name band '{lab}'"
    if not kind:
        if not synth:
            return set(), None, ""
        if synth & allowed:
            return synth, None, "master-education-level"
        return set(), None, f"master level '{raw}' dropped: contradicts Rule-6 stage"

    if kind == "range":
        if codes & allowed:
            return codes & allowed, None, label
        lv, _ = _match(LEVEL_RANGE, n)
        if lv & allowed:                      # band ∩ synthetic contradicts the stage: fall back to band ∩ stage
            return lv & allowed, None, f"scheme-name band ∩ Rule-6 stage (master level '{raw}' dropped)"
    if not codes - allowed:
        return codes, None, label
    # name signal is stronger than the Rule-6 stage: widen/replace the stage so every named level can pass
    need = set().union(*(LEVEL_STAGES[x] for x in codes))
    stage = need | (set(stage_set) if (stage_status == PARSED and codes & allowed) else set())
    return codes, stage, label + "; Rule-6 stage adjusted"


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
    elif cats and r.Category_Status == PARSED and set(r.category_set) != cats:
        # Update 3: the (synthetic) master names other categories than the scheme name -> the name wins.
        source = "name-overrides-master"
        why = why + [f"master said {r.Categories_Allowed}"]
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
    g = cur.get("gender") if cur and "gender" in cur else infer_gender(name)
    if r.Gender_Status == NO_REQ:
        if g and g != "All":
            upd.update(gender_set=frozenset({g}), Gender_Status=PARSED, Gender_Allowed=g, Gender_Source="inferred-name")
            notes.append(f"gender {g} [name]")
    elif r.Gender_Status == PARSED and g and set(r.gender_set) != ({g} if g != "All" else set()):
        # Update 3: the (synthetic) master gender contradicts the scheme name -> the name wins.
        if g == "All":
            upd.update(gender_set=frozenset(), Gender_Status=NO_REQ, Gender_Allowed="All")
        else:
            upd.update(gender_set=frozenset({g}), Gender_Allowed=g)
        upd["Gender_Source"] = "name-overrides-master"
        notes.append(f"gender {g} [name overrides master '{r.Gender_Raw}']")

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

    # ---- education level (finer than the Rule 6 stage)
    lv, stage, lv_source = resolve_education(name, r.Education_Level_Raw, r.Education_Stage_Status, r.stage_set)
    if lv:
        upd["Level_Codes"] = "; ".join(x for x in LEVELS if x in lv)
        notes.append(f"education level: {upd['Level_Codes']} [{lv_source}; raw='{r.Education_Level_Raw}']")
    elif lv_source:
        notes.append(f"education level: stage only [{lv_source}]")
    if stage:
        label = "; ".join(x for x in STAGES if x in stage)
        upd.update(stage_set=frozenset(stage), Education_Stage_Status=PARSED, Education_Stage_Allowed=label)
        notes.append(f"education stage: {label} [was '{r.Education_Stage_Raw}']")

    if not upd:
        return r
    upd["Overlay_Notes"] = " | ".join(notes)
    return replace(r, **upd)
