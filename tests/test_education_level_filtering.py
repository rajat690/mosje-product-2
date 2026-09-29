"""Regression tests for current-education filtering (29 Sep 2026 audit)."""
from app.eligibility.engine import EligibilityEngine, load_rules


def names(level):
    e = EligibilityEngine(load_rules())
    out = e.evaluate({
        "state": "Karnataka", "class_passed": level, "gender": "Male",
        "annual_family_income": 360000, "income_min": 120001, "category": "General",
    })
    return {x["name"] for x in out["schemes"]}


def test_pg_does_not_receive_aicte_swanath_degree_or_diploma():
    n = names("PG")
    assert "AICTE Swanath Scholarship Scheme - Degree" not in n
    assert "AICTE Swanath Scholarship Scheme - Diploma" not in n


def test_pg_does_not_receive_other_explicit_ug_or_diploma_schemes():
    n = names("PG")
    assert "AICTE Saksham Scholarship Scheme - Degree" not in n
    assert "AICTE Saksham Scholarship Scheme - Diploma" not in n
    assert "ICAR National Talent Scholarship (NTS-UG)" not in n


def test_pg_still_receives_explicit_pg_and_research_schemes():
    n = names("PG")
    assert "National Scholarship for Post Graduate Studies" in n
    assert "ICAR Post Graduate Scholarship (PGS)" in n
    assert "ICAR Junior Research Fellowship (JRF) and Senior Research Fellowship (SRF)" in n


def test_ug_and_diploma_routes_are_separated():
    ug = names("UG")
    xii = names("XII")
    assert "AICTE Swanath Scholarship Scheme - Degree" in ug
    assert "AICTE Swanath Scholarship Scheme - Diploma" not in ug
    assert "AICTE Swanath Scholarship Scheme - Diploma" in xii
    assert "AICTE Swanath Scholarship Scheme - Degree" not in xii
