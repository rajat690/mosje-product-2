"""Short display fields for scheme cards (Update 1, feedback 9).

Computed once when the master is compiled (tools/compile_master.py) and stored in data/scheme_rules_v3.json:
  Short_Description  <= 40 chars  from Benefits, else Programme Type
  Short_Eligibility  <= 50 chars  from the structured eligibility (category, gender, level, income, groups),
                                  else Other Eligibilities
  Short_Documents    <= 40 chars  from Documents Required
  Apply_URL                       Government Application Portal, else Official / Source URL
An empty value means the master has no data; the bot then shows "See official site" (translated).
Text is cut at a word boundary and ends with "…" when shortened.
"""
from __future__ import annotations

import re
from dataclasses import replace

from .rules_compiler import NO_REQ, PARSED, SchemeRule

DESC_MAX, ELIG_MAX, DOCS_MAX = 40, 50, 40
_BOILER = " The benefit is provided to eligible students"
GROUP_SHORT = {"disability": "students with disability", "farmer": "farmer families", "workers": "workers' children",
               "defence": "defence/police families", "school": "specific schools", "orphan": "orphans",
               "bpl": "BPL families", "teachers": "teachers' children", "other": "specific group"}
LEVEL_SHORT = {"PRE": "Class 1–10", "X": "Class 10 pass", "XII": "Class 12 pass", "UG": "UG", "PG": "PG/PhD"}


def given(v: str) -> str:
    v = (v or "").strip()
    low = v.lower()
    if not v or low.startswith("not specified") or low in {"n/a", "na", "-", "none", "nil"}:
        return ""
    return v


def shorten(text: str, limit: int) -> str:
    """Cut at a word boundary so that the result (including '…') fits in limit characters."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    sp = max(cut.rfind(" "), cut.rfind(","), cut.rfind(";"), cut.rfind("/"))
    if sp >= limit // 2:
        cut = cut[:sp]
    return cut.rstrip(" ,;:/-–(") + "…"


_PLACEHOLDER = re.compile(r"\s*Detailed scheme-specific conditions not yet verified\.?", re.I)


def clean_other(v: str) -> str:
    """Other Eligibilities without the master's placeholder sentence; 'Education stage: X' -> 'Course/stage: X'."""
    v = _PLACEHOLDER.sub("", given(v)).strip().rstrip(".")
    m = re.match(r"^Education stage:\s*(.+)$", v, re.I)
    if m:
        stage = m.group(1).strip()
        return "" if stage.lower() in {"education", ""} else f"Course/stage: {stage}"
    return v


def lakh(v: int) -> str:
    x = v / 100000
    return f"₹{x:g}L" if x >= 1 else f"₹{v:,}"


def eligibility_parts(r: SchemeRule) -> list[str]:
    parts = []
    if r.Category_Status == PARSED and r.category_set:
        parts.append("/".join(c for c in ("SC", "ST", "OBC", "General", "Minority") if c in r.category_set))
    if r.Gender_Status == PARSED and r.gender_set:
        g = sorted(r.gender_set)
        parts.append({"Female": "girls", "Male": "boys", "Transgender": "transgender"}.get(g[0], g[0])
                     if len(g) == 1 else "/".join(g))
    if r.Level_Codes:
        parts.append("/".join(LEVEL_SHORT[x] for x in r.Level_Codes.split("; ")))
    elif r.Education_Stage_Status == PARSED and r.Education_Stage_Allowed:
        parts.append(r.Education_Stage_Allowed.replace("; ", "/"))
    if r.Income_Status == PARSED and r.Income_Max:
        parts.append(f"income ≤ {lakh(r.Income_Max)}")
    for g in sorted(r.target_group_set):
        parts.append(GROUP_SHORT.get(g, g))
    return parts


def apply_display(r: SchemeRule) -> SchemeRule:
    src = []
    # description
    ben = given(r.Benefits)
    if ben and _BOILER in ben:
        ben = ben.split(_BOILER)[0].strip()
    ben = ben.rstrip(".").replace("...", "…")
    if ben:
        desc, src_d = shorten(ben, DESC_MAX), "benefits"
    elif given(r.Programme_Type):
        desc, src_d = shorten(given(r.Programme_Type), DESC_MAX), "programme_type"
    else:
        desc, src_d = "", "none"
    src.append(f"description={src_d}")
    # eligibility
    parts = eligibility_parts(r)
    if parts:
        elig, src_e = ", ".join(parts), "structured"
        if len(elig) > ELIG_MAX:
            while len(parts) > 1 and len(", ".join(parts)) > ELIG_MAX - 1:
                parts.pop()
            elig = shorten(", ".join(parts) + (", …" if len(parts) else ""), ELIG_MAX) \
                if len(", ".join(parts)) < len(elig) else shorten(elig, ELIG_MAX)
            elig = elig.replace(", …", "…")
    elif clean_other(r.Other_Eligibilities):
        elig, src_e = shorten(clean_other(r.Other_Eligibilities), ELIG_MAX), "other_eligibilities"
    elif r.Category_Status == NO_REQ and given(r.Category_Raw).lower().startswith("all"):
        elig, src_e = "All categories", "category_all"
    else:
        elig, src_e = "", "none"
    src.append(f"eligibility={src_e}")
    # documents
    docs = given(r.Documents_Required)
    src.append("documents=" + ("documents_required" if docs else "none"))
    docs = shorten(docs, DOCS_MAX) if docs else ""
    # URL
    url = ""
    for v in (r.Application_Portal, r.Source_URL):
        if v and v.strip().lower().startswith("http"):
            url = v.strip()
            break
    src.append("url=" + ("application_portal" if url and url == (r.Application_Portal or "").strip()
                         else "source_url" if url else "none"))
    return replace(r, Short_Description=desc, Short_Eligibility=elig, Short_Documents=docs, Apply_URL=url,
                   Short_Sources="; ".join(src))
