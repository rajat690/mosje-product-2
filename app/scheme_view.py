"""Rich scheme cards for the mobile web companion (Update 3).

Turns a SchemeRule + the student's answers into the fields the new UI shows on every card:
amount a year, last date + days left, "why you match" lines, an Eligible / Check-1-detail status,
a plain-word documents checklist, the official portal and the 3 steps to apply.

Text is returned as structured keys (e.g. {"k": "state", "x": "Karnataka"}) so the companion can show it in
the student's language. Nothing here changes who is eligible - that stays in app/eligibility/engine.py.

Optional data file: data/scheme_dates.csv (filled by the scheme-data owner, see templates/scheme_dates_template.csv)
    scheme_id,last_date,renewal,amount_per_year,last_verified,notes
The V3.0 master has no last-date / renewal columns, so without this file cards say "check official site"
and last-date reminders only run for dates a student enters in My schemes.
"""
from __future__ import annotations

import csv
import logging
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .eligibility.engine import (PARSED, SchemeRule, apply_where, check_groups_open, income_open, level_code,
                                 profile_from_facts, short_benefit)

log = logging.getLogger(__name__)
DATES_CSV = Path(__file__).resolve().parent.parent / "data" / "scheme_dates.csv"
IST = timezone(timedelta(hours=5, minutes=30))
CLOSING_SOON_DAYS = 15


def today_ist() -> date:
    return datetime.now(IST).date()


# ------------------------------------------------------------------ amount a year
_MONEY = r"₹\s?([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|l\b|k\b)?"
_PART = re.compile(_MONEY + r"\s*(/\s*month|per\s+month|a\s+month|p\.?m\.?|/\s*year|per\s+(?:year|annum)|a\s+year|"
                   r"annually|p\.?a\.?)?(?:\s*(?:fellowship|scholarship|stipend|allowance|assistance))?"
                   r"(?:\s*for\s+(\d{1,2})\s+months)?", re.I)


def _num(v: str, unit: str | None) -> float:
    n = float(v.replace(",", ""))
    u = (unit or "").lower()
    if u in ("lakh", "lac", "l"):
        n *= 100000
    elif u == "k":
        n *= 1000
    return n


_RANGE = re.compile(r"₹\s?[\d][\d,]*(?:\.\d+)?\s*(?:lakh|lac|l\b|k\b)?\s*(?:–|-|to)\s*(₹\s?[\d][\d,]*)", re.I)


def amount_per_year(benefits: str) -> tuple[Optional[int], str]:
    """'₹2,500/month for 10 months plus ₹5,000 book grant' -> (30000, 'year'). (None, '') if unknown.
    kind: 'year' (a yearly amount), 'once' (one-time award / incentive), 'total' (a total for the whole course, e.g.
    "Up to ₹15 lakh total overseas study assistance") - only 'year' amounts are used for "Up to ₹X a year".
    A range "₹5,000–₹20,000" counts as its upper end (the student sees "up to")."""
    b = (benefits or "").strip()
    if not b or b.lower().startswith("not specified") or "₹" not in b:
        return None, ""
    b = _RANGE.sub(lambda m: m.group(1), b)
    total, any_per, once, whole = 0.0, False, False, False
    for m in _PART.finditer(b):
        n = _num(m.group(1), m.group(2))
        per = (m.group(3) or "").lower()
        months = int(m.group(4)) if m.group(4) else None
        if "month" in per or per.startswith("p.m") or per == "pm":
            total += n * (months or 12)
            any_per = True
        elif per:
            total += n
            any_per = True
        else:
            near = (b[max(0, m.start() - 40):m.start()] + " " + b[m.end():m.end() + 30]).lower()
            if months:
                total += n * months
                any_per = True
            else:
                total += n
                if re.search(r"one[- ]time|\bonce\b|lump ?sum|\baward\b|incentive", near):
                    once = True
                if re.search(r"\btotal\b|whole course|entire course|full course", near):
                    whole = True
    if not total:
        return None, ""
    kind = "year" if any_per else ("total" if whole else ("once" if once else "year"))
    return int(round(total)), kind


# ------------------------------------------------------------------ documents
DOC_RULES = [
    ("aadhaar", r"aadhaar|aadhar"),
    ("domicile", r"domicile|residence|resident|niwas"),
    ("income", r"income"),
    ("caste", r"caste|community|tribe certificate"),
    ("marks", r"marksheet|mark sheet|marks card|marks"),
    ("fee", r"admission|enrol|fee receipt|bonafide|bona fide"),
    ("bank", r"bank|passbook"),
    ("class12", r"class\s*12|xii|12th"),
    ("research", r"research admission|phd admission|research"),
    ("degree", r"ug/pg|degree certificate|certificates"),
    ("photo", r"photo"),
    ("disability", r"disability|udid"),
]


def documents(rule: SchemeRule) -> list[dict]:
    raw = (rule.Documents_Required or "").strip()
    if not raw or raw.lower().startswith("not specified"):
        return []
    out, seen = [], set()
    for part in re.split(r"[;,]|\band\b", raw):
        p = part.strip(" .")
        if not p:
            continue
        key = next((k for k, rx in DOC_RULES if re.search(rx, p, re.I)), "other")
        if key in seen and key != "other":
            continue
        seen.add(key)
        out.append({"key": key, "raw": p})
    return out


# ------------------------------------------------------------------ last dates (optional data file)
@lru_cache(maxsize=1)
def scheme_dates() -> dict:
    out = {}
    if not DATES_CSV.exists():
        return out
    try:
        with open(DATES_CSV, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                sid = (row.get("scheme_id") or "").strip()
                if not sid:
                    continue
                rec = {"renewal": (row.get("renewal") or "").strip().lower() or None,
                       "last_verified": (row.get("last_verified") or "").strip() or None}
                try:  # "renewal" may be yes / no or the next renewal date (YYYY-MM-DD)
                    rec["renewal_date"] = date.fromisoformat(rec["renewal"]) if rec["renewal"] else None
                    rec["renewal"] = "yes"
                except ValueError:
                    rec["renewal_date"] = None
                try:
                    rec["last_date"] = date.fromisoformat((row.get("last_date") or "").strip()) if row.get("last_date") else None
                except ValueError:
                    rec["last_date"] = None
                try:
                    rec["amount_per_year"] = int(float(row["amount_per_year"])) if (row.get("amount_per_year") or "").strip() else None
                except ValueError:
                    rec["amount_per_year"] = None
                out[sid] = rec
    except Exception as e:  # noqa: BLE001
        log.warning("Could not read %s: %s", DATES_CSV, e)
    return out


def days_left(d: Optional[date], today: Optional[date] = None) -> Optional[int]:
    return None if d is None else (d - (today or today_ist())).days


# ------------------------------------------------------------------ why you match
LEVEL_NAMES = {"PRE": "PRE", "X": "X", "XII": "XII", "UG": "UG", "PG": "PG"}


def why_lines(rule: SchemeRule, facts: dict) -> list[dict]:
    p = profile_from_facts(facts)
    out = []
    if rule.Scheme_Level != "Central":
        out.append({"k": "state", "x": rule.Scheme_State_UT})
    elif rule.region_set:
        out.append({"k": "region", "x": rule.Region_States})
    if rule.Category_Status == PARSED and p.Social_Category:
        out.append({"k": "cat", "x": p.Social_Category})
    if rule.Gender_Status == PARSED and p.Gender == "Female" and rule.gender_set == frozenset({"Female"}):
        out.append({"k": "girl"})
    lv = level_code(p.Class_Passed)
    if lv and (rule.level_code_set or rule.Education_Stage_Status == PARSED):
        out.append({"k": "edu", "x": lv})
    if rule.Income_Status == PARSED and rule.Income_Max:
        out.append({"k": "inc_check" if income_open(p, rule) else "inc", "x": int(rule.Income_Max)})
    if rule.Age_Status == PARSED and (rule.Age_Raw or "").strip():
        out.append({"k": "age", "x": rule.Age_Raw.strip()})       # age is never asked: shown, never used to hide
    if not out:
        out.append({"k": "open"})
    return out


def portal_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or ""
    except ValueError:
        return ""


def card(rule: SchemeRule, facts: dict, rank: int | None = None, today: Optional[date] = None) -> dict:
    p = profile_from_facts(facts)
    groups = check_groups_open(p, rule)
    extra = scheme_dates().get(rule.Scheme_ID, {})
    amt, kind = amount_per_year(rule.Benefits)
    if extra.get("amount_per_year"):
        amt, kind = extra["amount_per_year"], "year"
    ld = extra.get("last_date")
    url = apply_where(rule)
    dl = days_left(ld, today)
    return {
        "rank": rank, "scheme_id": rule.Scheme_ID, "name": rule.Scheme_Name,
        "level": rule.Scheme_Level, "state_ut": rule.Scheme_State_UT,
        "is_state": rule.Scheme_Level != "Central",
        "department": (rule.Department or "").strip() if not (rule.Department or "").lower().startswith("not specified") else "",
        "amount_per_year": amt, "amount_kind": kind, "benefit": short_benefit(rule, limit=160),
        "short_description": rule.Short_Description, "short_eligibility": rule.Short_Eligibility,
        "last_date": ld.isoformat() if ld else None, "days_left": dl,
        "closing_soon": dl is not None and 0 <= dl <= CLOSING_SOON_DAYS,
        "closed": dl is not None and dl < 0,
        "renewal": extra.get("renewal"), "last_verified": extra.get("last_verified"),
        "status": "check" if groups else "eligible",
        "check": [{"k": g, "x": int(rule.Income_Max) if g == "income" and rule.Income_Max else None} for g in groups],
        "why": why_lines(rule, facts),
        "documents": documents(rule),
        "apply_url": url, "portal": portal_domain(url),
        "apply_url_verified": bool(rule.Application_Portal and rule.Application_Portal.lower().startswith("http")),
    }


def detail(rule: SchemeRule, facts: dict, today: Optional[date] = None) -> dict:
    from .eligibility.engine import scheme_detail
    d = card(rule, facts, today=today)
    sd = scheme_detail(rule)
    d.update({"benefit_full": sd["benefit"], "programme_type": sd["type"], "education": sd["stage"],
              "category_rule": sd["category"], "gender_rule": sd["gender"], "income_max": sd["income_max"],
              "income_raw": sd["income_raw"], "age_rule": sd["age"], "domicile": sd["domicile"],
              "other_conditions": sd["other"], "documents_raw": sd["documents"]})
    return d


def max_amount(cards: list[dict]) -> Optional[dict]:
    """The biggest single yearly amount among the student's results ("Up to ₹X a year").
    Amounts are never added together - a student usually gets one scholarship at a time. Eligible schemes count first;
    only when no eligible scheme shows a yearly amount do the "check 1 detail" schemes count."""
    yearly = [c for c in cards if c.get("amount_per_year") and c.get("amount_kind") == "year"]
    pool = [c for c in yearly if c.get("status") == "eligible"] or yearly
    if not pool:
        return None
    best = max(pool, key=lambda c: c["amount_per_year"])
    return {"amount": best["amount_per_year"], "scheme_id": best["scheme_id"], "name": best["name"],
            "status": best.get("status")}


def summary(cards: list[dict]) -> dict:
    known = [c for c in cards if c["amount_per_year"] and c["amount_kind"] == "year"]
    best = max_amount(cards)
    dated = sorted((c for c in cards if c["days_left"] is not None and c["days_left"] >= 0), key=lambda c: c["days_left"])
    return {"count": len(cards),
            "eligible": sum(1 for c in cards if c["status"] == "eligible"),
            "to_check": sum(1 for c in cards if c["status"] == "check"),
            "closing_soon": sum(1 for c in cards if c["closing_soon"]),
            "state_schemes": sum(1 for c in cards if c["is_state"]),
            # Shown to students as "Up to ₹X a year" (biggest single scheme, amounts are not added up).
            "max_per_year": best["amount"] if best else None,
            "max_scheme_id": best["scheme_id"] if best else None,
            "max_scheme_name": best["name"] if best else None,
            # DEPRECATED (kept so existing API users don't break): plain sum of every yearly amount. Not shown anywhere
            # in the student UI any more - a student cannot normally hold all these scholarships together.
            "total_per_year": sum(c["amount_per_year"] for c in known) if known else None,
            "amounts_known": len(known),
            "closest": ({"scheme_id": dated[0]["scheme_id"], "name": dated[0]["name"], "last_date": dated[0]["last_date"],
                         "days_left": dated[0]["days_left"]} if dated else None)}
