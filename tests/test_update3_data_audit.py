"""Update 3 (29 Sep 2026): clickable portal link after consent is declined + scheme data audit regressions."""
import re
import sys
from pathlib import Path

import pytest

from conftest import EN, HI, WA
from test_update1 import chat, web_session

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


# ------------------------------------------------------------------ Task 1: clickable link
def test_web_declined_reply_has_clean_portal_url_and_link(client):
    sid, tok, _ = web_session(client)
    chat(client, sid, tok, EN)
    r = chat(client, sid, tok, "disagree")["reply"]
    assert r["state"] == "DECLINED"
    assert "https://scholarships.gov.in/" in r["text"] and "gov.in/ ." not in r["text"]
    assert r["ui"]["external_links"][0]["url"] == "https://scholarships.gov.in/"


ALPHA = ["as", "bn", "bho", "en", "gu", "hi", "kn", "mai", "ml", "mr", "or", "pa", "ta", "te"]   # language list order


def test_whatsapp_declined_sends_plain_url_in_all_languages(client):
    for i, lang in enumerate(["en", "hi", "bn", "ta"]):
        wa = WA(client, f"91970000210{i}")
        wa.send("hi")
        wa.send(str(ALPHA.index(lang) + 1))
        out = wa.send("disagree")
        assert "https://scholarships.gov.in/" in out, lang
        assert wa.last[-1]["type"] in ("interactive", "text")              # sent fine; r.ui is ignored on WhatsApp


def test_companion_linkifies_urls_safely():
    html = (ROOT / "app" / "static" / "companion.html").read_text(encoding="utf-8")
    assert "function linkify(" in html and "createTextNode" in html
    body = html[html.index("function linkify("):html.index("function textMsg(")]
    assert "innerHTML" not in body                                           # DOM text nodes only
    assert 'rel = "noopener noreferrer"' in html and 'target = "_blank"' in html
    assert 'textMsg("msg bot", shown)' in html
    assert "already a link in the text" in html                              # no duplicate portal button


# ------------------------------------------------------------------ Task 2: scheme data audit
@pytest.fixture(scope="module")
def engine():
    from app.eligibility.engine import EligibilityEngine, load_rules
    return EligibilityEngine(load_rules())


def names(engine, **f):
    base = dict(state="Karnataka", class_passed="PG", gender="Male", category="General",
                annual_family_income=360000, income_min=120001)
    base.update(f)
    return [s["name"] for s in engine.evaluate(base)["schemes"]]


def test_no_name_vs_data_contradictions_left(engine):
    from scheme_data_audit import mismatches
    bad = [(r.Scheme_ID, m) for r in engine.rules if r.Active_Status == "ACTIVE" for m in mismatches(r)]
    assert bad == []


def test_every_active_scheme_is_reachable_by_some_level(engine):
    from scheme_data_audit import reachable_levels
    assert [r.Scheme_ID for r in engine.rules if r.Active_Status == "ACTIVE" and not reachable_levels(r)] == []


def test_karnataka_pg_profile_has_only_pg_or_open_schemes(engine):
    n = names(engine)
    for bad in ["AICTE Swanath Scholarship Scheme - Degree", "AICTE Swanath Scholarship Scheme - Diploma",
                "ICAR National Talent Scholarship (NTS-UG)", "AICTE Pragati Scholarship Scheme - Degree"]:
        assert bad not in n
    assert "ICAR National Talent Scholarship (NTS-PG)" in n and "National Scholarship for Post Graduate Studies" in n


def test_level_name_signals(engine):
    assert "Swami Vivekananda Merit-cum-Means Scholarship (SVMCM) - General Degree" not in \
        names(engine, state="West Bengal", class_passed="PG", category="General")
    assert "Swami Vivekananda Merit-cum-Means Scholarship (SVMCM) - General Degree" in \
        names(engine, state="West Bengal", class_passed="UG", category="General", annual_family_income=120000,
              income_min=None)
    xii = names(engine, state="Rajasthan", class_passed="XII", gender="Female", category="ST",
                annual_family_income=120000, income_min=None)
    assert "Kali Bai Bheel Medhavi Chhatra Scooty Yojana - Passed Class 12" in xii
    assert "Kali Bai Bheel Medhavi Chhatra Scooty Yojana - Passed Class 10" not in xii
    pre = names(engine, state="Karnataka", class_passed="PRE", category="General", annual_family_income=120000,
                income_min=None)
    assert "National Means-cum-Merit Scholarship Scheme (NMMSS)" in pre
    assert not any("Prime Minister's Scholarship Scheme" in x for x in pre)


def test_category_and_gender_name_overrides(engine):
    r = engine.by_id
    assert r["MSM-0084"].category_set == frozenset({"General"})              # EBC (Rajasthan) - master said OBC
    assert r["MSM-0007"].category_set == frozenset({"OBC", "General"})       # OBC, EBC and DNT
    assert r["MSM-0032"].category_set == frozenset({"OBC"})                  # Bihar BC/EBC are OBC lists
    assert r["MSM-0208"].category_set == frozenset({"SC"})                   # 'General' = stream, not category
    assert r["MSM-0544"].Gender_Status == "NO_REQUIREMENT"                   # Balak/Balika = boys and girls
    assert "name-overrides-master" in r["MSM-0084"].Overlay_Notes


def test_card_length_limits_80_80_90(engine):
    for r in engine.rules:
        assert len(r.Short_Description or "") <= 80
        assert len(r.Short_Eligibility or "") <= 80
        assert len(r.Short_Documents or "") <= 90
