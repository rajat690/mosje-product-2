import re
"""Update 2 (29 Sep 2026): State/UT is question 1, no Main menu on the summary and after the results,
compact scheme listing (details only on 'View details'), detail card with exactly 3 CTAs."""
from pathlib import Path

from conftest import EN, HI, WA, wa_answers, wa_start


def chat(client, sid, tok, text):
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text}, headers={"X-Session-Token": tok})
    assert r.status_code == 200, r.text
    return r.json()


def agreed(client, lang="en"):
    d = client.post("/v1/chat/sessions", json={"language": lang}).json()
    sid, tok = d["session_id"], d["session_token"]
    return sid, tok, chat(client, sid, tok, "agree")["reply"]


def finish(client, lang="en", answers=("Rajasthan", "2", "2", "1", "1")):
    sid, tok, _ = agreed(client, lang)
    for m in answers:
        chat(client, sid, tok, m)
    return sid, tok, chat(client, sid, tok, "proceed")["reply"]


def test_state_is_question_one_then_education_gender_income_category(client):
    sid, tok, q1 = agreed(client)
    assert q1["state"] == "ASK_state" and q1["text"].startswith("(1/5) Which state's scholarships would you like to see?")
    assert [o["id"] for o in q1["options"]][-2:] == ["back", "menu"]            # questions keep Go back / Main menu
    seen = []
    for m, want in [("Rajasthan", "(2/5)"), ("2", "(3/5)"), ("2", "(4/5)"), ("1", "(5/5)")]:
        r = chat(client, sid, tok, m)["reply"]
        assert r["text"].startswith(want), (m, r["text"][:40])
        seen.append(r["state"])
    assert seen == ["ASK_class_passed", "ASK_gender", "ASK_annual_family_income", "ASK_category"]
    summary = chat(client, sid, tok, "1")["reply"]
    assert summary["state"] == "SUMMARY"
    lines = [x for x in summary["text"].splitlines() if x.startswith("• ")]
    assert [x.split(":")[0] for x in lines] == ["• State/UT", "• Education level", "• Gender", "• Family income", "• Category"]
    assert [o["id"] for o in summary["options"]] == ["proceed", "edit"]          # no Main menu button


def test_edit_details_restarts_at_state_keeping_language_and_consent(client):
    sid, tok, _ = agreed(client, "hi")
    for m in ["Bihar", "2", "1", "1", "1"]:
        chat(client, sid, tok, m)
    edit = chat(client, sid, tok, "edit")["reply"]
    assert edit["state"] == "ASK_state" and edit["language"] == "hi" and "(1/5)" in edit["text"]
    assert "Bihar" in edit["text"]                                                # current answer shown as a hint
    r = client.get(f"/v1/chat/sessions/{sid}", headers={"X-Session-Token": tok}).json()["result"]
    assert r["consent"]["status"] == "AGREED" and r["answers"] == {}              # answers cleared, consent kept


def test_other_education_still_ends_early(client):
    sid, tok, _ = agreed(client)
    chat(client, sid, tok, "Goa")
    out = chat(client, sid, tok, "6")["reply"]                                    # Other / not studying
    assert out["state"] == "ENDED" and "Class 1 up to Post Graduation" in out["text"]


def test_no_main_menu_button_after_results(client):
    sid, tok, res = finish(client)
    ids = lambda r: [o["id"] for o in r["options"]]
    assert "menu" not in ids(res)
    det = chat(client, sid, tok, "1")["reply"]
    assert ids(det) == ["back", "share", "rate"]
    share = chat(client, sid, tok, "share")["reply"]
    assert ids(share) == ["back", "rate"]
    rating = chat(client, sid, tok, "rate")["reply"]
    assert "menu" not in ids(rating)
    comment = chat(client, sid, tok, "4")["reply"]
    assert "menu" not in ids(comment)
    shared = chat(client, sid, tok, "SKIP")["reply"]
    assert ids(shared) == ["list"]
    why = chat(client, sid, tok, "why are you showing me these schemes?")["reply"]
    assert why["view"] == "WHY" and "menu" not in ids(why)
    assert chat(client, sid, tok, "menu")["reply"]["state"] == "MENU"            # typing MENU still works


def test_compact_listing_web_and_whatsapp(client):
    sid, tok, res = finish(client)
    c = res["cards"][0]
    assert c["title_line"].startswith(c["name"]) and c["tag"] and "view_label" in c
    item = next(o for o in res["options"] if o["id"] == str(c["rank"]))
    assert item["desc"] == " · ".join(x for x in (c["tag"], c["department"]) if x)   # name · tag · department only
    html = (Path(__file__).resolve().parent.parent / "app" / "static" / "companion.html").read_text(encoding="utf-8")
    assert "L.description" not in html and "c.eligibility" not in html and "c.check_note" not in html
    assert 'el("div", "dept", c.department)' in html
    wa = WA(client, "919711100001")
    wa_start(wa)
    final = wa_answers(wa, edu="2", gender="2", income="1", category="1", state="Rajasthan")
    assert re.search(r"\*\d\. Post-Matric Scholarship for SC Students · Central", final)   # compact card line
    for gone in ("Description:", "Eligibility:", "Required documents:", "Application:"):
        assert gone not in final
    rows = [r for m in wa.last if m["type"] == "interactive"
            for s in m["interactive"]["action"]["sections"] for r in s["rows"]]
    assert all(r["id"] != "menu" for r in rows)


def test_detail_has_short_fields_and_whatsapp_three_buttons(client):
    sid, tok, res = finish(client)
    det = chat(client, sid, tok, "1")["reply"]["detail"]
    assert [x["key"] for x in det["short"]] == ["description", "eligibility", "documents", "url"]
    assert det["rows"]                                                              # "More details"
    wa = WA(client, "919711100002")
    wa_start(wa)
    wa_answers(wa, edu="2", gender="2", income="1", category="1", state="Rajasthan")
    out = wa.tap("1")
    btn = wa.last[-1]["interactive"]
    assert btn["type"] == "button" and [b["reply"]["id"] for b in btn["action"]["buttons"]] == ["back", "share", "rate"]
    assert "Type MENU for the main menu." in out and "Eligibility:" in out
    assert "Main menu" not in out


def test_state_question_translated_in_every_language():
    from app.conversation.texts import EN as EN_T, LANG_CODES, T
    assert EN_T["q_state"] == "Which state's scholarships would you like to see?"
    for L in LANG_CODES:
        q = T[L]["q_state"]
        assert q and len(q) <= 200 and (L == "en" or q != EN_T["q_state"]), L
        assert "निवासी" not in q and "domicile" not in q                          # old wording gone


def test_hindi_listing_compact(client):
    wa = WA(client, "919711100003")
    wa_start(wa, lang=HI)
    final = wa_answers(wa, edu="2", gender="2", income="2", category="1", state="Bihar")
    assert "छात्रवृत्ति" in final and "पात्रता:" not in final and "आवेदन:" not in final
    assert "मुख्य मेनू" not in final
