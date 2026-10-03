"""Update 3 (2 Oct 2026): the /companion page in English + Indian languages, State names translated, and
"Up to ₹X a year" wording. Language packs live in app/static/companion/lang/<code>.json (machine-drafted)."""
import json
import re
from pathlib import Path

import pytest

from conftest import make_client

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "app" / "static" / "companion"
FULL = ["bn", "mr", "ta", "te", "kn"]            # full UI packs (Hindi is inline in strings.js)
PH = re.compile(r"\{\w+\}")


def _strings():
    src = (COMP / "strings.js").read_text(encoding="utf-8")
    body = src[src.index("var T={") + 6: src.rindex("};") + 1]
    return json.loads(re.sub(r'^ (\w+):', r' "\1":', body, flags=re.M))


def _doc_keys():
    app = (COMP / "app.js").read_text(encoding="utf-8")
    block = app[app.index("var DOCS={"): app.index("};", app.index("var DOCS={"))]
    return set(re.findall(r"^ (\w+):\{n:", block, flags=re.M))


def _pack(code):
    return json.loads((COMP / "lang" / f"{code}.json").read_text(encoding="utf-8"))


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    yield c
    c.__exit__(None, None, None)


def test_english_and_hindi_inline_strings_are_complete():
    T = _strings()
    assert len(T) > 200
    for k, v in T.items():
        assert v[0] and v[1], k
        assert sorted(PH.findall(v[0])) == sorted(PH.findall(v[1])), k
    assert T["upTo"][0] == "Up to {x} a year" and "{x}" in T["upTo"][1]
    assert "totalGet" not in T


@pytest.mark.parametrize("code", FULL)
def test_language_pack_complete_and_placeholders_kept(code):
    T, p = _strings(), _pack(code)
    assert "MACHINE-DRAFTED" in p["_about"]
    assert set(p["strings"]) == set(T), set(T) ^ set(p["strings"])
    for k, v in p["strings"].items():
        assert v.strip(), k
        assert sorted(PH.findall(v)) == sorted(PH.findall(T[k][0])), (code, k, v)
        assert not re.search(r"[\u0966-\u096F\u09E6-\u09EF\u0BE6-\u0BEF\u0C66-\u0C6F\u0CE6-\u0CEF]", v), (code, k)
    assert set(p["docs"]) == _doc_keys()
    assert all(set(d) == {"n", "p", "w", "c", "t"} for d in p["docs"].values())
    assert len(p["months"]) == 12


@pytest.mark.parametrize("code", FULL + ["hi"])
def test_every_state_name_is_translated(code, app_client):
    states = app_client.get("/v1/companion/config").json()["states"]
    st = _pack(code)["states"]
    assert set(states) <= set(st), set(states) - set(st)
    assert all(v and not re.search(r"[A-Za-z]", v) for v in st.values())


def test_language_pack_endpoint(app_client):
    r = app_client.get("/companion/lang/ta.json")
    assert r.status_code == 200 and r.json()["strings"]["upTo"].count("{x}") == 1
    assert "max-age" in r.headers.get("cache-control", "")
    assert app_client.get("/companion/lang/hi.json").json()["states"]["Rajasthan"] == "राजस्थान"
    assert app_client.get("/companion/lang/xx.json").status_code == 404
    assert app_client.get("/companion/lang/..%2Fapp.json").status_code == 404
    page = app_client.get("/companion").text
    assert len(page.encode("utf-8")) < 200_000            # packs are loaded on demand, not inlined
    assert "/companion/lang/" in page and "Noto Sans Tamil" in page


def test_state_typed_in_indian_script_is_understood(app_client):
    d = app_client.post("/v1/chat/sessions", json={"language": "hi"}).json()
    sid, h = d["session_id"], {"X-Session-Token": d["session_token"]}
    app_client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "agree"}, headers=h)
    for typed, want in [("राजस्थान", "Rajasthan"), ("தமிழ்நாடு", "Tamil Nadu"), ("পশ্চিমবঙ্গ", "West Bengal")]:
        r = app_client.post(f"/v1/companion/sessions/{sid}/interpret", json={"key": "state", "text": typed}, headers=h)
        assert r.status_code == 200 and r.json()["understood"] and r.json()["send"] == want, r.text


def test_amount_kinds_total_once_and_ranges_are_not_counted_as_a_year():
    from app import scheme_view as V
    assert V.amount_per_year("Up to ₹15 lakh total overseas study assistance") == (1500000, "total")
    assert V.amount_per_year("One-time merit award of ₹10,000") == (10000, "once")
    assert V.amount_per_year("Merit award of ₹5,000–₹20,000 based on level") == (20000, "once")   # range -> upper end
    assert V.amount_per_year("₹2,500/month for 10 months plus ₹5,000 book grant") == (30000, "year")
    assert V.amount_per_year("₹35,000/month fellowship plus ₹25,000/year contingency") == (445000, "year")
    assert V.amount_per_year("Not specified") == (None, "")


def test_refer_message_is_in_the_students_language(app_client):
    from app.conversation.texts import LANG_CODES, t
    assert all("{link}" in t(c, "share_invite") for c in LANG_CODES)
    d = app_client.post("/v1/chat/sessions", json={"language": "ta"}).json()
    r = app_client.post(f"/v1/companion/sessions/{d['session_id']}/referral", json={},
                        headers={"X-Session-Token": d["session_token"]})
    assert r.status_code == 200, r.text
    msg = r.json()["share_message"]
    assert "உதவித்தொகை" in msg and "ref=REF-" in msg
