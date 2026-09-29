"""Product 2 eligibility engine (Scholarship Eligibility Rule V3.0).

Check logic COPIED from the Product 1 reference engine (not imported) and adapted for
Discovery: the student's facts come from their own answers (or from a referral pushed by a
Product 1), not from Jan Aadhaar.

Six mandatory AND checks, bulk order + fail-fast per section 7.9:
    1 Jurisdiction -> 2 Education Stage -> 3 Social Category -> 4 Gender -> 5 Family Income -> 6 Age
Anything that cannot be evaluated is FAIL (V3.0 has no referral / manual outcome).
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, fields
from datetime import date, datetime
from functools import lru_cache
from typing import Optional

from . import settings
from .rules_compiler import NO_REQ, PARSED, UNRES, SchemeRule, compile_master

log = logging.getLogger(__name__)

PASS, FAIL, NOT_EVAL = "PASS", "FAIL", "NOT_EVALUATED (fail-fast)"
ELIGIBLE, NOT_ELIGIBLE = "ELIGIBLE", "NOT ELIGIBLE"


# ------------------------------------------------------------------ student profile (7.2)
def derive_education_stage(class_passed) -> Optional[frozenset]:
    c = str(class_passed or "").strip().upper().replace("CLASS", "").strip()
    if c in {"X", "10", "10TH"}:
        return frozenset({"Post-Matric"})
    if c in {"XII", "12", "12TH"}:
        return frozenset({"Post-Matric", "Higher Education"})
    return None


def completed_years(dob_iso: Optional[str], as_of: date) -> Optional[int]:
    """Equivalent of Excel DATEDIF(DOB, as_of, "Y")."""
    if not dob_iso:
        return None
    d = datetime.strptime(dob_iso, "%Y-%m-%d").date()
    return as_of.year - d.year - ((as_of.month, as_of.day) < (d.month, d.day))


@dataclass
class StudentProfile:
    Student_ID: str
    Domicile_State_UT: Optional[str]
    DOB: Optional[str]
    Calculated_Age: Optional[int]
    Gender: Optional[str]
    Annual_Family_Income: Optional[int]
    Social_Category: Optional[str]
    Student_Education_Stage: Optional[frozenset]
    Class_Passed: str = ""


def profile_from_facts(facts: dict, student_id: str = "discovery", as_of: date | None = None) -> StudentProfile:
    """facts keys (all optional): state, class_passed, category, gender, annual_family_income, dob."""
    as_of = as_of or settings.as_of_date()
    inc = facts.get("annual_family_income")
    try:
        inc = int(float(inc)) if inc not in (None, "") else None
    except (TypeError, ValueError):
        inc = None
    dob = facts.get("dob") or None
    return StudentProfile(
        Student_ID=student_id,
        Domicile_State_UT=facts.get("state") or None,
        DOB=dob,
        Calculated_Age=completed_years(dob, as_of) if dob else None,
        Gender=facts.get("gender") or None,
        Annual_Family_Income=inc,
        Social_Category=facts.get("category") or None,
        Student_Education_Stage=derive_education_stage(facts.get("class_passed")),
        Class_Passed=str(facts.get("class_passed") or ""),
    )


# ------------------------------------------------------------------ individual checks
def check_jurisdiction(p: StudentProfile, s: SchemeRule):
    if s.Scheme_Level == "Central":
        return PASS, ""
    if p.Domicile_State_UT and p.Domicile_State_UT.lower() == s.Scheme_State_UT.lower():
        return PASS, ""
    return FAIL, f"Jurisdiction: scheme is for {s.Scheme_State_UT}; student domicile {p.Domicile_State_UT or 'unknown'}"


def check_education_stage(p: StudentProfile, s: SchemeRule):
    if p.Student_Education_Stage is None:
        return FAIL, "Education Stage: class passed not known"
    if s.Education_Stage_Status == NO_REQ:
        return PASS, ""
    if s.Education_Stage_Status == UNRES:
        return FAIL, f"Education Stage: scheme wording '{s.Education_Stage_Raw}' not a controlled value"
    if p.Student_Education_Stage & s.stage_set:
        return PASS, ""
    return FAIL, "Education Stage: student stage not allowed by scheme"


def check_category(p: StudentProfile, s: SchemeRule):
    if s.Category_Status == NO_REQ:
        return PASS, ""
    if s.Category_Status == UNRES:
        return FAIL, f"Social Category: scheme wording '{s.Category_Raw}' cannot be resolved"
    if not p.Social_Category:
        return FAIL, "Social Category: student category not known"
    if p.Social_Category in s.category_set:
        return PASS, ""
    return FAIL, f"Social Category: scheme allows {s.Categories_Allowed}; student is {p.Social_Category}"


def check_gender(p: StudentProfile, s: SchemeRule):
    if s.Gender_Status == NO_REQ:
        return PASS, ""
    if s.Gender_Status == UNRES:
        return FAIL, f"Gender: scheme wording '{s.Gender_Raw}' unclear"
    if not p.Gender:
        return FAIL, "Gender: student gender not known"
    if p.Gender in s.gender_set:
        return PASS, ""
    return FAIL, f"Gender: scheme is for {s.Gender_Allowed}; student is {p.Gender}"


def check_income(p: StudentProfile, s: SchemeRule):
    if s.Income_Status == NO_REQ:
        return PASS, ""
    if s.Income_Status == UNRES:
        return FAIL, f"Family Income: condition stated ('{s.Income_Raw}') but no numeric ceiling"
    if p.Annual_Family_Income is None:
        return FAIL, "Family Income: not known"
    if p.Annual_Family_Income <= s.Income_Max:
        return PASS, ""
    return FAIL, f"Family Income: {p.Annual_Family_Income:,} > ceiling {s.Income_Max:,}"


def check_age(p: StudentProfile, s: SchemeRule):
    if s.Age_Status == NO_REQ:
        return PASS, ""
    if s.Age_Status == UNRES:
        return FAIL, f"Age: condition '{s.Age_Raw}' cannot be converted to a min/max age"
    if p.Calculated_Age is None:
        return FAIL, "Age: date of birth not known"
    if s.Age_Min is not None and p.Calculated_Age < s.Age_Min:
        return FAIL, f"Age: {p.Calculated_Age} < minimum {s.Age_Min}"
    if s.Age_Max is not None and p.Calculated_Age > s.Age_Max:
        return FAIL, f"Age: {p.Calculated_Age} > maximum {s.Age_Max}"
    return PASS, ""


BULK_ORDER = [("Education_Stage_Result", check_education_stage),
              ("Social_Category_Result", check_category),
              ("Gender_Result", check_gender),
              ("Income_Result", check_income),
              ("Age_Result", check_age)]


def evaluate_pair(p: StudentProfile, s: SchemeRule, fail_fast: bool = True) -> dict:
    out = {"Scheme_ID": s.Scheme_ID, "Scheme_Name": s.Scheme_Name}
    res, reason = check_jurisdiction(p, s)
    out["Domicile_Result"] = res
    reasons = [reason] if reason else []
    failed = res == FAIL
    for col, fn in BULK_ORDER:
        if failed and fail_fast:
            out[col] = NOT_EVAL
            continue
        res, reason = fn(p, s)
        out[col] = res
        if res == FAIL:
            failed = True
            reasons.append(reason)
    out["Final_Result"] = NOT_ELIGIBLE if failed else ELIGIBLE
    out["Failure_Reason"] = "; ".join(reasons)
    out["Rule_Version"] = settings.RULE_VERSION
    return out


# ------------------------------------------------------------------ scheme presentation helpers
_BOILER = " The benefit is provided to eligible students"


def short_benefit(s: SchemeRule, limit: int = 110) -> str:
    b = (s.Benefits or "").strip()
    if not b or b.lower().startswith("not specified"):
        return ""
    if _BOILER in b:
        b = b.split(_BOILER)[0].strip()
    return b if len(b) <= limit else b[: limit - 1].rstrip() + "…"


def apply_where(s: SchemeRule) -> str:
    for v in (s.Application_Portal, s.Source_URL):
        if v and v.lower().startswith("http"):
            return v
    return ""


def scheme_card(s: SchemeRule, rank: int) -> dict:
    return {"rank": rank, "scheme_id": s.Scheme_ID, "name": s.Scheme_Name,
            "level": s.Scheme_Level, "state_ut": s.Scheme_State_UT,
            "benefit": short_benefit(s), "apply_url": apply_where(s),
            "apply_url_verified": bool(s.Application_Portal and s.Application_Portal.lower().startswith("http")),
            "documents": (s.Documents_Required or "")[:200]}


def _rank_key(s: SchemeRule):
    score = 0
    if s.Category_Status == PARSED:
        score += 2          # targeted at the student's category
    if s.Gender_Status == PARSED:
        score += 1
    if s.Scheme_Level != "Central":
        score += 1          # state schemes are less known, surface them
    if s.Application_Portal.lower().startswith("http"):
        score += 1
    if short_benefit(s):
        score += 1
    return (-score, s.Scheme_Name.lower())


# ------------------------------------------------------------------ engine
class EligibilityEngine:
    def __init__(self, rules: list[SchemeRule]):
        self.all_rules = rules
        self.rules = [r for r in rules if r.Active_Status == "ACTIVE"]
        self.by_id = {r.Scheme_ID: r for r in self.rules}
        self.CENTRAL_SCHEMES = [r for r in self.rules if r.Scheme_Level == "Central"]
        self.STATE_UT_SCHEMES = defaultdict(list)
        for r in self.rules:
            if r.Scheme_Level != "Central":
                self.STATE_UT_SCHEMES[r.Scheme_State_UT.lower()].append(r)

    # which facts can change an outcome with the loaded master ("minimum questions")
    def needed_facts(self) -> list[str]:
        need = ["class_passed", "state", "category"]
        if any(r.Gender_Status == PARSED for r in self.rules):
            need.append("gender")
        if any(r.Income_Status == PARSED for r in self.rules):
            need.append("annual_family_income")
        if any(r.Age_Status == PARSED for r in self.rules):
            need.append("dob")
        return need

    def states(self) -> list[str]:
        return sorted({r.Scheme_State_UT for r in self.rules if r.Scheme_Level != "Central"})

    def candidate_schemes(self, p: StudentProfile) -> list[SchemeRule]:
        dom = (p.Domicile_State_UT or "").lower()
        return self.CENTRAL_SCHEMES + (self.STATE_UT_SCHEMES.get(dom, []) if dom else [])

    def evaluate(self, facts: dict) -> dict:
        p = profile_from_facts(facts)
        audits, eligible = [], []
        for s in self.candidate_schemes(p):
            a = evaluate_pair(p, s)
            audits.append(a)
            if a["Final_Result"] == ELIGIBLE:
                eligible.append(s)
        eligible.sort(key=_rank_key)
        return {"rule_version": settings.RULE_VERSION,
                "as_of": settings.as_of_date().isoformat(),
                "candidate_schemes_checked": len(audits),
                "eligible_count": len(eligible),
                "schemes": [scheme_card(s, i + 1) for i, s in enumerate(eligible)],
                "audit": audits}


# ------------------------------------------------------------------ loading
_SET_FIELDS = ("stage_set", "gender_set", "category_set")


def rule_to_json(r: SchemeRule) -> dict:
    d = r.export_dict()
    d["stage_set"] = sorted(r.stage_set)
    d["gender_set"] = sorted(r.gender_set)
    d["category_set"] = sorted(r.category_set)
    return d


def rule_from_json(d: dict) -> SchemeRule:
    names = {f.name for f in fields(SchemeRule)}
    kw = {k: v for k, v in d.items() if k in names}
    for k in _SET_FIELDS:
        kw[k] = frozenset(d.get(k) or [])
    return SchemeRule(**kw)


def write_rules_json(rules: list[SchemeRule], path=None):
    path = path or settings.SCHEME_RULES_JSON
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"rule_version": settings.RULE_VERSION, "source": settings.SCHEME_MASTER_PATH.name,
                   "count": len(rules), "rules": [rule_to_json(r) for r in rules]}, f, ensure_ascii=False, indent=1)


def load_rules() -> list[SchemeRule]:
    if settings.SCHEME_RULES_JSON.exists():
        with open(settings.SCHEME_RULES_JSON, encoding="utf-8") as f:
            return [rule_from_json(d) for d in json.load(f)["rules"]]
    log.warning("Compiled scheme rules not found; compiling from %s", settings.SCHEME_MASTER_PATH)
    return compile_master(settings.SCHEME_MASTER_PATH)


@lru_cache(maxsize=1)
def get_engine() -> EligibilityEngine:
    return EligibilityEngine(load_rules())
