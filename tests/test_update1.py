"""Update 1 (29 Sep 2026): category overlay, detail cards, navigation, 14 languages, WhatsApp interactive,
language-first + consent, max 5 questions, summary, short display fields, share scheme, star feedback."""
import string

import pytest

from conftest import BN, EN, HI, KEY_RAJAT, WA, H, make_client, wa_answers, wa_start

KARNATAKA_GENERAL = dict(state="Karnataka", class_passed="X", category="General", gender="Male",
                         annual_family_income=450000)
WRONG_FOR_GENERAL = ["Backward Classes Fee Reimbursement - Karnataka", "Backward Classes Post-Matric Scholarship - Karnataka",
                     "Free Coaching for SCs, OBCs and Beneficiaries of PM CARES Children Scheme",
                     "Vidyasiri Food and Accommodation Scholarship Scheme - Backward Classes Karnataka",
                     "AICTE Pragati Scholarship Scheme - Diploma"]


def chat(client, sid, tok, text):
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text}, headers={"X-Session-Token": tok})
    assert r.status_code == 200, r.text
    return r.json()


def web_session(client, lang=None):
    d = client.post("/v1/chat/sessions", json={"language": lang} if lang else {}).json()
    return d["session_id"], d["session_token"], d["reply"]


def web_agreed(client, lang="en"):
    """Web session with the language given -> consent -> Agree. Returns sid, tok, reply (first question)."""
    sid, tok, first = web_session(client, lang)
    assert first["state"] == "CONSENT"
    return sid, tok, chat(client, sid, tok, "agree")["reply"]


# ------------------------------------------------------------------ feedback 1: category bug
def test_general_student_no_longer_sees_reserved_category_schemes():
    from app.eligibility import get_engine
    res = get_engine().evaluate(dict(KARNATAKA_GENERAL, disability=False))
    names = [c["name"] for c in res["schemes"]]
    for bad in WRONG_FOR_GENERAL:
        assert bad not in names
    assert "AICTE Saksham Scholarship Scheme - Diploma" not in names           # disability: No
    farmer = next(c for c in res["schemes"] if "Farmer Family" in c["name"])
    assert farmer["only_for"] == ["farmer"] and farmer["check"] is True        # shown only as "check eligibility"
    assert all(c["check"] for c in res["schemes"])                              # nothing unconditional left


def test_obc_student_still_sees_backward_class_schemes_and_ranking():
    from app.eligibility import get_engine
    res = get_engine().evaluate(dict(KARNATAKA_GENERAL, category="OBC", disability=None))
    names = [c["name"] for c in res["schemes"]]
    assert "Backward Classes Post-Matric Scholarship - Karnataka" in names
    checks = [c["check"] for c in res["schemes"]]
    assert checks == sorted(checks)                                             # unconditional first, check-group last
    saksham = next(c for c in res["schemes"] if "Saksham" in c["name"])
    assert saksham["only_for"] == ["disability"]                               # prefer not to say -> check
    yes = get_engine().evaluate(dict(KARNATAKA_GENERAL, disability=True))
    assert next(c for c in yes["schemes"] if "Saksham" in c["name"])["check"] is False


def test_overlay_inference_rules():
    from app.eligibility.overlay import infer_categories, infer_gender, infer_groups
    assert infer_categories("Post-Matric Scholarship for SC Students")[0] == {"SC"}
    assert infer_categories("Pre-SSC Scholarship - Nomadic and Denotified Tribes Gujarat")[0] == {"OBC"}
    assert infer_categories("Merit Scholarships for Economically Backward Class Students")[0] == {"General"}
    assert infer_categories("Aikyashree Minority Scholarship")[0] == {"Minority"}
    assert infer_categories("Pre-SSC Scholarship for Class 9")[0] == set()          # 'SSC' is not 'SC'
    assert infer_categories("Scholarship for Std XI")[0] == set()                   # 'Std' is not 'ST'
    assert infer_gender("Bicycle to Girls Studying in Std IX") == "Female"
    assert infer_gender("Mukhyamantri Balak/Balika Protsahan Yojana") is None
    assert infer_groups("Financial Assistance to Children of Armed Forces Personnel Killed/Disabled in War", "") == {"defence"}
    assert infer_groups("Post-Matric Scholarship for Students with Disabilities", "") == {"disability"}


def test_overlay_applied_to_compiled_rules_and_audit_fields():
    from app.eligibility import get_engine
    e = get_engine()
    r = e.by_id["MSM-0273"]
    assert r.category_set == frozenset({"OBC"}) and r.Category_Source == "inferred-name" and r.Overlay_Notes
    assert e.by_id["MSM-0069"].gender_set == frozenset({"Female"})
    ne = e.by_id["MSM-0016"]
    assert "Assam" in ne.region_set
    assert e.evaluate(dict(KARNATAKA_GENERAL, disability=False))["candidate_schemes_checked"] > 0
    audit = e.evaluate(dict(KARNATAKA_GENERAL, state="Assam", disability=False))["audit"]
    assert any(a["Scheme_ID"] == "MSM-0016" and a["Domicile_Result"] == "PASS" for a in audit)
    audit = e.evaluate(dict(KARNATAKA_GENERAL, disability=False))["audit"]
    assert any(a["Scheme_ID"] == "MSM-0016" and a["Domicile_Result"] == "FAIL" for a in audit)
    assert "Target_Group_Result" in audit[0] and "disability" not in e.needed_facts()    # max 5 questions


def test_category_audit_report_exists():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    md = (root / "docs" / "CATEGORY_AUDIT.md").read_text(encoding="utf-8")
    assert "Before / after" in md and "Backward Classes Post-Matric Scholarship - Karnataka" in md
    assert (root / "docs" / "category_audit.csv").exists()


# ------------------------------------------------------------------ feedback 1: free-text fallback
def test_why_free_text_gets_friendly_explanation(client):
    wa = WA(client, "919700000001")
    wa_start(wa)
    wa_answers(wa, edu="2", gender="1", income="3", category="4", state="Karnataka")
    out = wa.send("i am a general caste student. why are you showing me SC, ST, OBC schemes?")
    assert "didn't get" not in out and "did not understand" not in out
    assert "saved category is General" in out and "Edit details" in out
    out = wa.send("actually I am OBC")
    assert "You mentioned OBC" in out
    out = wa.tap("setcat:OBC")
    assert "Updated Category: OBC" in out and "Please check your details" in out     # summary again
    assert "Backward Classes Post-Matric Scholarship - Karnataka" in wa.send("1")


def test_unknown_text_fallback_keeps_options(client):
    sid, tok, _ = web_agreed(client)
    out = chat(client, sid, tok, "banana")["reply"]
    assert out["text"].startswith("I didn't get that") and "MENU, BACK or HELP" in out["text"]
    assert out["state"] == "ASK_state" and [o["id"] for o in out["options"]][:3] == ["1", "2", "3"]
    assert out["options"][-1]["id"] == "menu"                        # Main menu kept on the questions


# ------------------------------------------------------------------ feedback 6/7: language first, consent
def test_language_first_alphabetical_with_native_script(client):
    from app.conversation.texts import LANG_ORDER, LANGS
    sid, tok, first = web_session(client)
    assert first["state"] == "LANG" and first["ui"]["dropdown"] is True and first["ui"]["continue"] == "Continue"
    labels = [o["label"] for o in first["options"]]
    english = [LANGS[o["code"]]["en"] for o in first["options"]]
    assert english == sorted(english) and [o["code"] for o in first["options"]] == LANG_ORDER
    assert labels[:4] == ["অসমীয়া (Assamese)", "বাংলা (Bengali)", "भोजपुरी (Bhojpuri)", "English"]
    wa = WA(client, "919700000010")
    wa.send("hi")
    rows = [r["title"] for s in wa.last[-1]["interactive"]["action"]["sections"] for r in s["rows"]]
    assert rows[:4] == ["অসমীয়া (Assamese)", "বাংলা (Bengali)", "भोजपुरी (Bhojpuri)", "English"]


def test_consent_agree_records_timestamp(client):
    sid, tok, first = web_session(client)
    consent = chat(client, sid, tok, EN)["reply"]
    assert consent["state"] == "CONSENT" and [o["id"] for o in consent["options"]][:2] == ["agree", "disagree"]
    assert "I will not ask for your name, Aadhaar" in consent["text"]
    assert chat(client, sid, tok, "agree")["reply"]["state"] == "ASK_state"
    r = client.get(f"/v1/chat/sessions/{sid}", headers={"X-Session-Token": tok}).json()["result"]
    assert r["consent"]["status"] == "AGREED" and r["consent"]["at"].endswith("Z")
    assert r["consent"]["version"].startswith("p2-consent-")


def test_consent_declined_stores_nothing_personal(client):
    from app import db as dbm
    from app.db import ChatSession, Message
    wa = WA(client, "919700000011")
    wa.send("hi")
    wa.send(HI)
    out = wa.send("2")                                            # Don't agree
    assert "scholarships.gov.in" in out and "अब सहमत हूँ" in out
    wa.send("I am SC, my income is 5000")                         # typed after declining -> not stored
    s = dbm.SessionLocal()
    try:
        sess = s.query(ChatSession).filter_by(wa_id="919700000011").order_by(ChatSession.id.desc()).first()
        assert sess.consent_status == "DECLINED" and sess.consent_at is not None and sess.status == "CONSENT_DECLINED"
        assert not any(not k.startswith("_") for k in (sess.answers or {}))
        texts = [m.body for m in s.query(Message).filter_by(session_id=sess.id, direction="in").all()]
        assert "I am SC, my income is 5000" not in texts and any("not stored" in (t or "") for t in texts)
    finally:
        s.close()
    assert "(1/5)" in wa.send("1")                                 # changed mind: Agree now -> first question


def test_referral_declined_consent_marks_referral(client):
    client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [
        {"external_ref": "C-1", "mobile": "9876566666", "name": "Asha", "state": "Bihar", "class_passed": "X",
         "category": "SC", "gender": "Female", "annual_family_income": 100000}]})
    wa = WA(client, "919876566666")
    wa.send("hi")
    wa.send(EN)
    wa.send("disagree")
    ref = client.get("/v1/referrals/C-1", headers=H(KEY_RAJAT)).json()
    assert ref["status"] == "CONSENT_DECLINED"


# ------------------------------------------------------------------ feedback 5/8: five questions + summary
def test_five_questions_then_summary_edit_and_proceed(client):
    sid, tok, q = web_agreed(client)
    assert q["text"].startswith("(1/5)")
    states = []
    for m in ["Kerala", "4", "2", "2", "5"]:                       # Kerala, UG, Female, ₹10,001–30,000, Minority
        states.append(chat(client, sid, tok, m)["reply"]["state"])
    assert states == ["ASK_class_passed", "ASK_gender", "ASK_annual_family_income", "ASK_category", "SUMMARY"]
    summary = chat(client, sid, tok, "menu")["reply"]              # menu then back to the summary
    assert chat(client, sid, tok, "back")["reply"]["state"] == "SUMMARY"
    edit = chat(client, sid, tok, "edit")["reply"]                 # Edit details -> question 1 (State) again
    assert edit["state"] == "ASK_state" and "Your current answer: Kerala" in edit["text"]
    for m in ["Kerala", "5", "2", "2", "5"]:
        out = chat(client, sid, tok, m)["reply"]
    assert out["state"] == "SUMMARY" and "Post Graduation (PG)" in out["text"] and "₹10,001–₹30,000 a month" in out["text"]
    res = chat(client, sid, tok, "proceed")
    assert res["status"] == "COMPLETED" and res["reply"]["state"] == "RESULTS"
    r = client.get(f"/v1/chat/sessions/{sid}", headers={"X-Session-Token": tok}).json()["result"]
    a = r["answers"]
    assert a["class_passed"] == "PG" and a["income_band"] == "m30k"
    assert a["annual_family_income"] == 360000 and a["income_min"] == 120001
    assert "disability" not in a


def test_income_band_straddling_ceiling_is_check_eligibility():
    from app.eligibility import get_engine
    e = get_engine()
    # ₹10,001–30,000 a month = ₹1.2–3.6 lakh a year: a ₹2.5 lakh ceiling may or may not apply -> "check"
    res = e.evaluate(dict(state="Rajasthan", class_passed="X", category="SC", gender="Female",
                          annual_family_income=360000, income_min=120001))
    pm = next(c for c in res["schemes"] if c["name"] == "Post-Matric Scholarship for SC Students")
    assert pm["check"] is True and "income" in pm["only_for"]
    low = e.evaluate(dict(state="Rajasthan", class_passed="X", category="SC", gender="Female", annual_family_income=120000))
    assert next(c for c in low["schemes"] if c["name"] == "Post-Matric Scholarship for SC Students")["check"] is False
    high = e.evaluate(dict(state="Rajasthan", class_passed="X", category="SC", gender="Female",
                           annual_family_income=None, income_min=360001))
    assert "Post-Matric Scholarship for SC Students" not in [c["name"] for c in high["schemes"]]


def test_education_levels_use_master_level_overlay():
    from app.eligibility import get_engine
    e = get_engine()
    base = dict(state="Karnataka", category="SC", gender="Male", annual_family_income=120000)
    names = lambda lvl: {c["scheme_id"] for c in e.evaluate(dict(base, class_passed=lvl))["schemes"]}
    pg, ug, pre = names("PG"), names("UG"), names("PRE")
    pg_only = {r.Scheme_ID for r in e.rules if r.level_code_set == {"PG"}}
    assert pg_only and pg_only & pg and not (pg_only & ug)             # PG-only schemes never shown to UG students
    assert not (pg_only & pre) and pre != ug
    from app import facts as F
    assert [F.norm_class(x) for x in ["Graduation", "pg", "9", "Class 10", "12th", "other"]] == \
        ["UG", "PG", "PRE", "X", "XII", "OTHER"]


# ------------------------------------------------------------------ feedback 9: display format + short fields
def test_short_fields_within_limits_for_every_scheme():
    from app.eligibility import get_engine
    for r in get_engine().rules:
        assert len(r.Short_Description) <= 40 and len(r.Short_Eligibility) <= 50 and len(r.Short_Documents) <= 40, r.Scheme_ID
        assert r.Apply_URL.startswith("http")
        for v in (r.Short_Description, r.Short_Eligibility, r.Short_Documents):
            assert not v or not v.endswith(" …")


def _finish_web(client, lang="en", answers=("Rajasthan", "2", "2", "1", "1")):
    sid, tok, _ = web_agreed(client, lang)
    for m in answers:
        chat(client, sid, tok, m)
    return sid, tok, chat(client, sid, tok, "proceed")


def test_list_cards_and_detail_card(client):
    sid, tok, out = _finish_web(client)
    rep = out["reply"]
    c = rep["cards"][0]
    assert c["tag"] in ("Central", "Rajasthan") and c["view_label"] == "View details"
    assert c["title_line"].startswith(c["name"]) and c["tag"] in c["title_line"]
    assert c["description"] and c["eligibility"] and c["documents"] and c["url"]
    assert c["labels"] == {"description": "Description", "eligibility": "Eligibility", "documents": "Required documents",
                           "url": "Application"}
    det = chat(client, sid, tok, str(c["rank"]))["reply"]                      # typing the number opens the card
    assert det["state"] == "DETAIL" and det["detail"]["title"] == c["name"]
    assert [x["key"] for x in det["detail"]["short"]] == ["description", "eligibility", "documents", "url"]
    keys = [r["key"] for r in det["detail"]["rows"]]
    for k in ("type", "benefit", "stage", "category", "gender", "income", "domicile", "other", "deadline"):
        assert k in keys
    assert all(r["value"] for r in det["detail"]["rows"])                       # never blank
    deadline = next(r for r in det["detail"]["rows"] if r["key"] == "deadline")
    assert deadline["value"] == "Not available – check official site" and deadline["na"]
    assert "This is guidance only" in det["detail"]["note"] and "This is guidance only" in det["text"]
    assert [o["id"] for o in det["options"]] == ["back", "share", "rate"]         # Update 2: no Main menu
    assert chat(client, sid, tok, "back")["reply"]["state"] == "RESULTS"         # Go back -> the list


def test_detail_for_scheme_with_full_master_data(client):
    sid, tok, out = _finish_web(client)
    rank = next(c["rank"] for c in out["reply"]["cards"] if c["name"] == "Post-Matric Scholarship for SC Students")
    det = chat(client, sid, tok, str(rank))["reply"]["detail"]
    rows = {r["key"]: r["value"] for r in det["rows"]}
    short = {r["key"]: r["value"] for r in det["short"]}
    assert rows["category"] == "SC" and rows["income"] == "up to ₹2,50,000 a year"
    assert "₹13,500" in rows["benefit"] and "income certificate" in short["documents"]
    assert short["url"] == "https://scholarships.gov.in/" and det["apply_url_verified"]
    assert len(short["description"]) <= 40 and len(short["eligibility"]) <= 50


# ------------------------------------------------------------------ feedback 10/11: share scheme + star feedback
def test_share_scheme_message_and_links(client):
    sid, tok, out = _finish_web(client)
    chat(client, sid, tok, "1")
    sh = chat(client, sid, tok, "share")["reply"]
    assert sh["state"] == "SHARE" and [o["id"] for o in sh["options"]] == ["back", "rate"]
    share = sh["share"]
    code = share["share_code"]
    assert code.startswith("REF-") and code in share["message"] and "src=referral&ref=" + code in share["message"]
    assert share["whatsapp_share_url"].startswith("https://wa.me/?text=") and share["email_url"].startswith("mailto:?subject=")
    assert set(share["labels"]) >= {"whatsapp", "email", "copy", "more", "copied"}
    assert chat(client, sid, tok, "back")["reply"]["state"] == "DETAIL"
    # a friend opening the web link is attributed as a peer referral
    d = client.post("/v1/chat/sessions", json={"entry": {"src": "referral", "ref": code}}).json()
    assert d["entry_source"] == "PEER_REFERRAL"


def test_whatsapp_share_scheme_sends_forwardable_message_first(client):
    wa = WA(client, "919700000012")
    wa_start(wa)
    wa_answers(wa, edu="2", gender="2", income="1", category="1", state="Rajasthan")
    wa.tap("1")
    btn = wa.last[-1]["interactive"]
    assert [b["reply"]["id"] for b in btn["action"]["buttons"]] == ["back", "share", "rate"]   # Main menu by typing
    assert "Type MENU" in "\n".join(client.graph.as_text(j) for j in wa.last)
    wa.tap("share")
    first, second = wa.last[-2], wa.last[-1]
    assert first["type"] == "text" and "REF-" in first["text"]["body"] and "wa.me" in first["text"]["body"]
    assert second["type"] == "interactive" and "Forward" in second["interactive"]["body"]["text"]


def test_star_rating_feedback(client):
    sid, tok, _ = _finish_web(client)
    chat(client, sid, tok, "1")
    fb = chat(client, sid, tok, "rate")["reply"]                    # Share Feedback from the detail card
    assert fb["state"] == "FEEDBACK_RATING"
    items = [o for o in fb["options"] if o["kind"] == "item"]
    assert [o["label"] for o in items] == ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    assert items[0]["desc"] == "1 – Very poor" and items[4]["desc"] == "5 – Excellent"
    assert chat(client, sid, tok, "⭐⭐⭐")["reply"]["state"] == "FEEDBACK_COMMENT"
    out = chat(client, sid, tok, "Good list")["reply"]
    assert out["state"] == "SHARED"
    r = client.get(f"/v1/chat/sessions/{sid}", headers={"X-Session-Token": tok}).json()["result"]
    assert r["feedback"] == {"rating": 3, "comment": "Good list"}


# ------------------------------------------------------------------ feedback 3: navigation
def test_back_preserves_answers_and_menu(client):
    sid, tok, _ = web_agreed(client)
    chat(client, sid, tok, "Kerala")
    chat(client, sid, tok, "2")                                   # Class 10 passed
    chat(client, sid, tok, "1")                                   # Male
    back = chat(client, sid, tok, "back")["reply"]
    assert back["state"] == "ASK_gender" and "Your current answer: Male" in back["text"]
    back = chat(client, sid, tok, "back")["reply"]
    assert back["state"] == "ASK_class_passed" and "Class 10 passed" in back["text"]
    assert chat(client, sid, tok, "2")["reply"]["state"] == "ASK_annual_family_income"  # gender kept -> next unanswered
    for m in ["1", "4"]:
        chat(client, sid, tok, m)
    res = chat(client, sid, tok, "proceed")["reply"]
    assert res["state"] == "RESULTS"
    menu = chat(client, sid, tok, "menu")["reply"]
    assert menu["state"] == "MENU" and [o["id"] for o in menu["options"]] == ["find", "change", "lang", "help", "rate", "back"]
    ch = chat(client, sid, tok, "change")["reply"]                # Edit details -> restart at question 1 (State)
    assert ch["state"] == "ASK_state"
    assert chat(client, sid, tok, "menu")["reply"]["options"][0]["label"] == "Find scholarships"


def test_language_switch_from_menu_returns_to_previous_view(client):
    sid, tok, _ = web_agreed(client)
    chat(client, sid, tok, "Kerala")
    chat(client, sid, tok, "2")
    chat(client, sid, tok, "language")
    out = chat(client, sid, tok, BN)["reply"]                      # বাংলা
    assert out["language"] == "bn" and out["state"] == "ASK_gender" and "লিঙ্গ" in out["text"]
    assert out["options"][-1]["label"] == "মূল মেনু"


# ------------------------------------------------------------------ feedback 4: languages
def test_all_languages_complete_and_button_limits():
    from app.conversation.texts import BUTTON_KEYS, EN as EN_T, LANG_CODES, ROW_KEYS, T, lang_label
    assert LANG_CODES == ["en", "hi", "bn", "as", "kn", "ta", "te", "ml", "or", "bho", "mai", "gu", "mr", "pa"]
    fmt = string.Formatter()
    for L in LANG_CODES:
        assert set(T[L]) == set(EN_T), L
        for k, v in T[L].items():
            assert v.strip(), (L, k)
            assert {p for _, p, _, _ in fmt.parse(v) if p} == {p for _, p, _, _ in fmt.parse(EN_T[k]) if p}, (L, k)
        for k in BUTTON_KEYS:
            assert len(T[L][k]) <= 20, (L, k, T[L][k])
        for k in ROW_KEYS:
            assert len(T[L][k]) <= 24, (L, k, T[L][k])
        assert len(lang_label(L)) <= 24


@pytest.mark.parametrize("code", ["hi", "bn", "as", "kn", "ta", "te", "ml", "or", "bho", "mai", "gu", "mr", "pa"])
def test_pick_each_language(client, code):
    from app.conversation.texts import LANG_ORDER, T
    sid, tok, first = web_session(client)
    assert len(first["options"]) == 14
    out = chat(client, sid, tok, str(LANG_ORDER.index(code) + 1))["reply"]
    assert out["language"] == code and out["state"] == "CONSENT" and T[code]["consent"] in out["text"]
    q = chat(client, sid, tok, "1")["reply"]
    assert q["state"] == "ASK_state" and T[code]["q_state"] in q["text"]


def test_whatsapp_payload_limits_in_every_language(client):
    """Walk every view in every language and check the Cloud API interactive limits."""
    from app.channels.whatsapp import build_messages
    from app.conversation.core import BotReply
    from app.conversation.texts import LANG_CODES
    fields = BotReply.__dataclass_fields__
    for code in LANG_CODES:
        sid, tok, r0 = web_session(client, code)
        replies = [r0]
        for m in ["agree", "Rajasthan", "2", "2", "1", "1", "back", "proceed", "proceed", "1", "share", "back", "back",
                  "menu", "change", "back", "rate", "back", "why is this wrong", "menu", "lang"]:
            replies.append(chat(client, sid, tok, m)["reply"])
        for r in replies:
            reply = BotReply(**{k: v for k, v in r.items() if k in fields})
            n_pages = 1
            page = 1
            while page <= n_pages:
                for p in build_messages(reply, page):
                    if p["type"] == "text":
                        assert len(p["text"]["body"]) <= 4096
                        continue
                    it = p["interactive"]
                    assert 0 < len(it["body"]["text"]) <= 1024, (code, r["view"])
                    if it["type"] == "button":
                        btns = it["action"]["buttons"]
                        assert 1 <= len(btns) <= 3
                        for b in btns:
                            assert len(b["reply"]["title"]) <= 20 and not b["reply"]["title"].endswith("…"), (code, b)
                    else:
                        act = it["action"]
                        assert len(act["button"]) <= 20
                        rows = [row for sec in act["sections"] for row in sec["rows"]]
                        assert 1 <= len(rows) <= 10, (code, r["view"], len(rows))
                        assert len({row["id"] for row in rows}) == len(rows)
                        for sec in act["sections"]:
                            assert len(sec["title"]) <= 24 and sec["rows"]
                        for row in rows:
                            assert len(row["title"]) <= 24 and len(row.get("description", "")) <= 72
                            if not row["id"].isdigit() and not row["id"].startswith("chg:"):
                                assert not row["title"].endswith("…"), (code, row)   # nav labels never cut
                            if row["id"].startswith("__pg:"):
                                n_pages = max(n_pages, int(row["id"][5:]))
                page += 1


def test_whatsapp_state_list_pagination(client):
    wa2 = WA(client, "919700000022")
    out = wa_start(wa2)                                           # Agree -> (1/5) State question (36 States/UTs)
    rows = [r for s in wa2.last[-1]["interactive"]["action"]["sections"] for r in s["rows"]]
    assert rows[-3]["id"] == "__pg:2" and len(rows) == 10 and "Andhra Pradesh" in out
    p2 = wa2.tap("__pg:2")
    rows2 = [r for s in wa2.last[-1]["interactive"]["action"]["sections"] for r in s["rows"]]
    assert "Page 2 of" in p2 and any(r["id"] == "__pg:1" for r in rows2) and any(r["id"] == "__pg:3" for r in rows2)
    tapped = next(r for r in rows2 if r["id"].isdigit())
    assert "(2/5)" in wa2.tap(tapped["id"])                       # tapping a State on page 2 answers it -> education


def test_whatsapp_interactive_can_be_disabled(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, WHATSAPP_INTERACTIVE="false")
    try:
        wa = WA(c, "919700000004")
        out = wa.send("hi")
        assert wa.last[-1]["type"] == "text" and "6. हिंदी (Hindi)" in out and "4. English" in out
    finally:
        c.__exit__(None, None, None)


def test_returning_whatsapp_user_keeps_language_and_consent(client):
    wa = WA(client, "919700000005")
    wa.send("hi")
    wa.send(BN)                                                    # Bengali
    from app.conversation.texts import T
    assert T["bn"]["q_state"] in wa.send("1")
    again = wa.send("hi")
    assert "নমস্কার" in again and "(1/5)" in again                  # restart: language + consent remembered


def test_referral_accepts_new_languages_and_disability_prefill(client):
    r = client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [
        {"external_ref": "BN-1", "mobile": "9876577777", "name": "Rupa Das", "state": "West Bengal", "class_passed": "XII",
         "category": "General", "gender": "Female", "annual_family_income": 200000, "disability": "no", "language": "bn"}]})
    assert r.status_code == 200 and not r.json().get("warnings")
    wa = WA(client, "919876577777")
    first = wa.send("hi")
    assert "নমস্কার Rupa" in first                                  # language known from the referral -> consent
    summary = wa.send("1")
    assert "West Bengal" in summary and "প্রতিবন্ধকতা" not in summary  # disability is kept for matching, not asked/shown
    assert "আপনার উত্তর" in wa.send("1")
    meta = client.get("/v1/meta", headers=H(KEY_RAJAT)).json()
    assert "bn" in meta["languages"] and len(meta["languages"]) == 14
    assert meta["questions_asked"] == ["state", "class_passed", "gender", "annual_family_income", "category"]
    assert meta["class_passed"] == ["PRE", "X", "XII", "UG", "PG"]


# ------------------------------------------------------------------ DB: safe additive schema upgrade
def test_ensure_schema_adds_missing_columns_without_data_loss(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from app import db as dbm
    url = f"sqlite:///{tmp_path}/old.db"
    eng = create_engine(url)
    dbm.Base.metadata.create_all(eng)
    with eng.begin() as c:                                          # simulate the older live schema
        c.execute(text("ALTER TABLE p2_sessions DROP COLUMN last_reply"))
        for col in ("consent_status", "consent_at", "consent_version"):     # Update 1 consent columns
            c.execute(text(f"ALTER TABLE p2_sessions DROP COLUMN {col}"))
        c.execute(text("INSERT INTO p2_sessions (public_id, channel, state, language, answers, prefilled, status, result_offset, "
                       "entry_source, started_at, updated_at) VALUES ('s_old', 'whatsapp', 'RESULTS', 'hi', '{}', '{}', "
                       "'COMPLETED', 5, 'ORGANIC', '2026-09-01 10:00:00', '2026-09-01 10:00:00')"))
    assert "last_reply" not in {c["name"] for c in inspect(eng).get_columns("p2_sessions")}
    ran = dbm.ensure_schema(eng)
    assert len(ran) == 4 and "last_reply" in ran[0]
    cols = {c["name"] for c in inspect(create_engine(url)).get_columns("p2_sessions")}
    assert {"last_reply", "consent_status", "consent_at", "consent_version"} <= cols
    with eng.begin() as c:
        assert c.execute(text("SELECT language, result_offset FROM p2_sessions WHERE public_id='s_old'")).one() == ("hi", 5)
    assert dbm.ensure_schema(eng) == []                            # idempotent
