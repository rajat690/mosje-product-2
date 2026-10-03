"""Update 3 (2 Oct 2026, Product Vision V1.0): mobile-first web companion, Save on WhatsApp (one tap / SAVE code /
parent OK), My schemes + tracker + reminders, feedback, refer a friend, typed answers, TTS/STT provision."""
import base64
from datetime import date, timedelta

import pytest

from conftest import ADMIN_KEY, EN, H, KEY_RAJAT, WA, make_client, wa_answers, wa_payload, wa_start

BASE = "https://p2.example.org"


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, PUBLIC_BASE_URL=BASE, WHATSAPP_DISPLAY_NUMBER="15550000000",
                    SPEECH_ENABLED="false", SPEECH_PROVIDER="none")
    yield c
    c.__exit__(None, None, None)
    from app import results
    results.TEST_TRANSPORT = None


@pytest.fixture
def speech_client(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, SPEECH_ENABLED="true", SPEECH_PROVIDER="mock")
    yield c
    c.__exit__(None, None, None)
    from app import results
    results.TEST_TRANSPORT = None


def chat(c, sid, tok, text):
    r = c.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text}, headers={"X-Session-Token": tok})
    assert r.status_code == 200, r.text
    return r.json()["reply"]


def web_done(c, answers=("Rajasthan", "2", "2", "1", "1"), entry=None):
    d = c.post("/v1/chat/sessions", json={"language": "en", "entry": entry or {}}).json()
    sid, tok = d["session_id"], d["session_token"]
    chat(c, sid, tok, "agree")
    for m in answers:
        chat(c, sid, tok, m)
    chat(c, sid, tok, "proceed")
    return sid, tok, {"X-Session-Token": tok}


# ------------------------------------------------------------------ companion page + config
def test_companion_page_is_the_new_mobile_ui_and_classic_is_kept(app_client):
    r = app_client.get("/companion")
    assert r.status_code == 200 and "Scholarship Discovery" in r.text
    assert "/*__CSS__*/" not in r.text and "//__JS__" not in r.text      # assembled from app/static/companion/
    assert "/v1/companion/" in r.text and len(r.content) < 200_000
    assert 'name="viewport"' in r.text
    assert app_client.get("/companion/classic").status_code == 200
    cfg = app_client.get("/v1/companion/config").json()
    assert len(cfg["languages"]) == 14 and "Rajasthan" in cfg["states"] and len(cfg["likely_states"]) == 6
    assert cfg["speech"]["enabled"] is False and cfg["wa_hi_link"].startswith("https://wa.me/15550000000")


def test_results_cards_details_and_own_state_first(app_client):
    sid, tok, h = web_done(app_client)
    res = app_client.get(f"/v1/companion/sessions/{sid}/results", headers=h).json()
    assert res["completed"] and res["cards"] and res["summary"]["count"] == len(res["cards"])
    assert [p["key"] for p in res["profile"]][0] == "state"
    own = [c["is_state"] for c in res["cards"]]                        # own State schemes before Central ones
    assert own == sorted(own, reverse=True)
    first = res["cards"][0]
    d = app_client.get(f"/v1/companion/sessions/{sid}/schemes/{first['scheme_id']}", headers=h).json()
    assert d["scheme_id"] == first["scheme_id"] and d["why"] and "documents" in d and "apply_url" in d
    assert app_client.get(f"/v1/companion/sessions/{sid}/schemes/NOPE", headers=h).status_code == 404
    assert app_client.get(f"/v1/companion/sessions/{sid}/results").status_code in (401, 403)


def test_summary_shows_up_to_biggest_single_amount_not_a_sum(app_client):
    """2 Oct decision: "Up to ₹X a year" = biggest single yearly amount among eligible results; never a sum."""
    from app import scheme_view as V
    sid, tok, h = web_done(app_client)
    res = app_client.get(f"/v1/companion/sessions/{sid}/results", headers=h).json()
    sm, cards = res["summary"], res["cards"]
    yearly = [c for c in cards if c["amount_per_year"] and c["amount_kind"] == "year"]
    elig = [c for c in yearly if c["status"] == "eligible"] or yearly
    assert yearly, "test profile should have schemes with a yearly amount"
    assert sm["max_per_year"] == max(c["amount_per_year"] for c in elig)
    assert sm["max_scheme_id"] in {c["scheme_id"] for c in elig if c["amount_per_year"] == sm["max_per_year"]}
    assert sm["total_per_year"] == sum(c["amount_per_year"] for c in yearly)   # deprecated field kept for API users
    if len(yearly) > 1:
        assert sm["max_per_year"] < sm["total_per_year"]
    # eligible schemes win over "check 1 detail" ones even when the check-only amount is bigger
    fake = [{"scheme_id": "A", "name": "A", "amount_per_year": 90000, "amount_kind": "year", "status": "check"},
            {"scheme_id": "B", "name": "B", "amount_per_year": 12000, "amount_kind": "year", "status": "eligible"},
            {"scheme_id": "C", "name": "C", "amount_per_year": 50000, "amount_kind": "once", "status": "eligible"}]
    assert V.max_amount(fake)["scheme_id"] == "B"
    assert V.max_amount(fake[:1])["amount"] == 90000                       # only check-only schemes -> use those
    assert V.max_amount(fake[2:]) is None                                  # one-time amounts are not "a year"
    page = app_client.get("/companion").text
    assert "upTo" in page and "total_per_year" not in page and "totalGet" not in page


# ------------------------------------------------------------------ typed answers + edit one answer
def test_typed_answers_are_understood_and_prefill(app_client):
    d = app_client.post("/v1/chat/sessions", json={"language": "en"}).json()
    sid, tok = d["session_id"], d["session_token"]
    chat(app_client, sid, tok, "agree")
    chat(app_client, sid, tok, "Bihar")
    r = chat(app_client, sid, tok, "I am in 2nd year BA")
    assert r["state"] == "ASK_gender"                                  # "2nd year BA" -> UG
    it = app_client.post(f"/v1/companion/sessions/{sid}/interpret", json={"text": "8000 per month"},
                         headers={"X-Session-Token": tok}).json()
    assert it["understood"] is False or it["key"] == "gender"
    it = app_client.post(f"/v1/companion/sessions/{sid}/interpret",
                         json={"text": "8000 per month", "key": "annual_family_income"},
                         headers={"X-Session-Token": tok}).json()
    assert it["understood"] and it["value"] == 96000


def test_edit_one_answer_from_the_review_card(app_client):
    d = app_client.post("/v1/chat/sessions", json={"language": "en"}).json()
    sid, tok = d["session_id"], d["session_token"]
    chat(app_client, sid, tok, "agree")
    for m in ("Rajasthan", "2", "2", "1"):
        chat(app_client, sid, tok, m)
    assert chat(app_client, sid, tok, "1")["state"] == "SUMMARY"
    r = chat(app_client, sid, tok, "edit:gender")
    assert r["state"] == "ASK_gender"
    r = chat(app_client, sid, tok, "1")
    assert r["state"] == "SUMMARY"                                     # straight back to the review, others kept
    assert "Rajasthan" in r["text"]


# ------------------------------------------------------------------ feedback + refer a friend
def test_feedback_is_stored_and_returns_refer_links(app_client):
    sid, tok, h = web_done(app_client)
    r = app_client.post(f"/v1/companion/sessions/{sid}/feedback",
                        json={"rating": 4, "comment": "Useful", "context": {"screen": "summary"}}, headers=h)
    assert r.status_code == 201, r.text
    ref = r.json()["refer"]
    assert ref["share_code"].startswith("REF-") and f"src=referral&ref={ref['share_code']}" in ref["web_link"]
    assert ref["whatsapp_share_url"].startswith("https://wa.me/?text=") and ref["share_message"]
    assert app_client.post(f"/v1/companion/sessions/{sid}/feedback", json={"rating": 9}, headers=h).status_code == 422
    fb = app_client.get("/v1/companion/feedback", headers=H(ADMIN_KEY)).json()
    assert fb["count"] == 1 and fb["feedback"][0]["comment"] == "Useful" and fb["feedback"][0]["channel"] == "web"
    assert fb["feedback"][0]["context"]["screen"] == "summary"
    assert app_client.get("/v1/companion/feedback").status_code == 401


def test_referral_link_tags_the_friend_as_peer_referral(app_client):
    sid, tok, h = web_done(app_client)
    ref = app_client.post(f"/v1/companion/sessions/{sid}/referral", json={"via": "whatsapp"}, headers=h).json()
    code = ref["share_code"]
    d = app_client.post("/v1/chat/sessions", json={"entry": {"src": "referral", "ref": code}}).json()
    assert d["entry_source"] == "PEER_REFERRAL"
    again = app_client.post(f"/v1/companion/sessions/{sid}/referral", json={}, headers=h).json()
    assert again["share_code"] == code and again["referrals_started"] >= 1
    f = app_client.get("/v1/companion/funnel", headers=H(ADMIN_KEY)).json()
    assert f["peer_referral_sessions"] >= 1 and f["sessions"] >= 2


def test_whatsapp_feedback_and_refer_flow(app_client):
    wa = WA(app_client, "919811100001")
    wa_start(wa, EN)
    wa_answers(wa)
    out = wa.send("refer")
    assert "REF-" in out
    wa.send("feedback")
    assert "comment" in wa.send("5").lower()
    assert "REF-" in wa.send("Very helpful")                           # thanks + refer links after feedback
    from app import db as dbm
    from app.db import Feedback
    with dbm.SessionLocal() as db:
        rows = db.query(Feedback).all()
        assert rows and rows[-1].rating == 5 and rows[-1].channel == "whatsapp"


# ------------------------------------------------------------------ journeys 1-2: one-time link + one-tap save
def test_hi_reply_offers_one_time_link_and_one_tap_save(app_client):
    wa = WA(app_client, "919811100002")
    wa.send("hi")
    out = wa.send(EN)
    assert f"{BASE}/companion?c=WL-" in out
    code = out.split("/companion?c=")[1].split()[0]
    wa.send("1")
    wa_answers(wa, proceed=True)
    o = app_client.post("/v1/companion/open", json={"code": code}).json()
    assert o["linked"] and o["phone_masked"].endswith("0002") and o["student_token"] is None
    h = {"X-Session-Token": o["session_token"]}
    assert o["status"] in ("ACTIVE", "COMPLETED")
    # same answers carried over -> results available
    sid = o["session_id"]
    res = app_client.get(f"/v1/companion/sessions/{sid}/results", headers=h).json()
    if not res["cards"]:
        chat(app_client, sid, o["session_token"], "proceed")
        res = app_client.get(f"/v1/companion/sessions/{sid}/results", headers=h).json()
    assert res["cards"] and res["linked_phone"]
    ids = [c["scheme_id"] for c in res["cards"][:2]]
    sv = app_client.post(f"/v1/companion/sessions/{sid}/save", json={"scheme_ids": ids, "consent": True}, headers=h)
    assert sv.status_code == 200, sv.text
    sv = sv.json()
    assert sv["status"] == "saved" and sv["saved"] == 2 and sv["student_token"]
    me = app_client.get("/v1/companion/me", headers={"X-Student-Token": sv["student_token"]}).json()
    assert len(me["saved"]) == 2 and me["phone_masked"].endswith("0002")
    # the link works once; a forwarded / reused link opens an anonymous page
    o2 = app_client.post("/v1/companion/open", json={"code": code}).json()
    assert o2["linked"] is False and o2["phone_masked"] is None and o2["reason"] == "link_used_or_expired"
    assert app_client.post("/v1/companion/open", json={"code": "WL-doesnotexist"}).json()["reason"] == "link_invalid"


def test_save_needs_consent(app_client):
    sid, tok, h = web_done(app_client)
    assert app_client.post(f"/v1/companion/sessions/{sid}/save", json={"consent": False},
                           headers=h).status_code == 400


# ------------------------------------------------------------------ journey 3: SAVE code from WhatsApp
def test_anonymous_web_save_with_code_sent_from_whatsapp(app_client):
    sid, tok, h = web_done(app_client)
    r = app_client.post(f"/v1/companion/sessions/{sid}/save",
                        json={"scope": "all", "consent": True, "phone": "98111 00003"}, headers=h).json()
    assert r["status"] == "confirm_pending" and r["code"].startswith("SAVE-") and r["code"] in r["wa_text"]
    assert r["wa_link"].startswith("https://wa.me/15550000000?text=")
    assert app_client.get(f"/v1/companion/sessions/{sid}/save-status/{r['code']}", headers=h).json()["status"] == "pending"
    wa = WA(app_client, "919811100003")
    out = wa.send(r["wa_text"])
    assert "Saved!" in out and f"{BASE}/companion?c=WL-" in out
    st = app_client.get(f"/v1/companion/sessions/{sid}/save-status/{r['code']}", headers=h).json()
    assert st["status"] == "confirmed" and st["student_token"] and st["me"]["saved"]
    st2 = app_client.get(f"/v1/companion/sessions/{sid}/save-status/{r['code']}", headers=h).json()
    assert "student_token" not in st2                                   # handed over once
    again = wa.send(r["wa_text"])                                       # reused code -> polite "not valid"
    assert again and "Saved!" not in again
    # "my schemes" on WhatsApp -> one-time link to My schemes
    out = wa.send("my schemes")
    assert f"{BASE}/companion?c=WL-" in out
    link = out.split("/companion?c=")[1].split()[0]
    o = app_client.post("/v1/companion/open", json={"code": link}).json()
    assert o["linked"] and o["screen"] == "my" and o["student_token"]


def test_under_18_parent_ok(app_client):
    sid, tok, h = web_done(app_client)
    r = app_client.post(f"/v1/companion/sessions/{sid}/save",
                        json={"scope": "all", "consent": True, "age_band": "u18", "phone": "9811100004"},
                        headers=h).json()
    assert r["status"] == "parent_pending" and r["code"].startswith("OK-")
    assert r["parent"]["whatsapp_share_url"].startswith("https://wa.me/?text=")
    parent = WA(app_client, "919811199999")
    parent.send(f"YES, I allow scholarship reminders for my child. Code {r['code']}")
    st = app_client.get(f"/v1/companion/sessions/{sid}/save-status/{r['code']}", headers=h).json()
    assert st["status"] == "confirmed" and st["phone_masked"].endswith("0004")
    me = app_client.get("/v1/companion/me", headers={"X-Student-Token": st["student_token"]}).json()
    assert me["age_band"] == "u18"


# ------------------------------------------------------------------ My schemes + tracker + reminders + delete
def _saved_student(c, phone="9811100005"):
    sid, tok, h = web_done(c)
    r = c.post(f"/v1/companion/sessions/{sid}/save", json={"scope": "all", "consent": True, "phone": phone},
               headers=h).json()
    wa = WA(c, "91" + phone)
    wa.send(r["wa_text"])
    c.wa = wa
    st = c.get(f"/v1/companion/sessions/{sid}/save-status/{r['code']}", headers=h).json()
    return {"X-Student-Token": st["student_token"]}, st["me"]


def test_tracker_dates_preferences_and_reminders(app_client):
    sh, me = _saved_student(app_client)
    sid0 = me["saved"][0]["scheme_id"]
    last = (date.today() + timedelta(days=7)).isoformat()
    r = app_client.patch(f"/v1/companion/me/schemes/{sid0}", json={"last_date": last}, headers=sh)
    assert r.status_code == 200 and r.json()["scheme"]["last_date"] == last
    kinds = [u["kind"] for u in r.json()["me"]["upcoming"]]
    assert "deadline_2" in kinds or "deadline_7" in kinds
    # dry run lists, real run cannot send outside the 24h window without a template -> NOT_SENT / sent
    out = app_client.post("/v1/jobs/run-reminders", json={"dry_run": True}, headers=H(ADMIN_KEY)).json()
    assert out["dry_run"] is True
    out = app_client.post("/v1/jobs/run-reminders", json={}, headers=H(ADMIN_KEY)).json()
    assert out["sent"] + out["not_sent"] >= 1                            # 7-day reminder is due today
    assert app_client.post("/v1/jobs/run-reminders", json={}, headers=H(KEY_RAJAT)).status_code == 403
    # Applied -> no more last-date reminders
    r = app_client.patch(f"/v1/companion/me/schemes/{sid0}", json={"status": "applied"}, headers=sh).json()
    assert r["scheme"]["status"] == "applied"
    assert not [u for u in r["me"]["upcoming"] if u["kind"].startswith("deadline") and u["scheme_id"] == sid0]
    assert app_client.patch(f"/v1/companion/me/schemes/{sid0}", json={"status": "nope"}, headers=sh).status_code == 422
    p = app_client.put("/v1/companion/me/preferences", json={"deadline": False, "new": False}, headers=sh).json()
    assert p["preferences"]["deadline"] is False and p["preferences"]["new"] is False and p["preferences"]["renew"] is True
    n = len(p["saved"])
    after = app_client.delete(f"/v1/companion/me/schemes/{sid0}", headers=sh).json()
    assert len(after["saved"]) == n - 1
    ref = app_client.post("/v1/companion/me/referral", json={"via": "copy"}, headers=sh).json()
    assert ref["share_code"].startswith("REF-")
    assert app_client.delete("/v1/companion/me", headers=sh).json()["deleted"] is True
    assert app_client.get("/v1/companion/me", headers=sh).status_code == 401


def test_stop_on_whatsapp_stops_reminders(app_client):
    sh, me = _saved_student(app_client, "9811100006")
    app_client.wa.send("STOP")                         # same WA helper (message ids must stay unique)
    from app import db as dbm
    from app.db import Student
    with dbm.SessionLocal() as db:
        assert db.query(Student).filter(Student.wa_id == "919811100006").one().status == "STOPPED"


# ------------------------------------------------------------------ speech (TTS / STT) provision
def test_speech_is_off_by_default_with_a_clear_message(app_client):
    s = app_client.get("/v1/speech/status").json()
    assert s["enabled"] is False and s["tts"] is False and s["stt"] is False
    r = app_client.post("/v1/speech/tts", json={"text": "Hello", "lang": "hi"})
    assert r.status_code == 503 and r.json()["detail"]["error"] == "speech_not_configured"
    r = app_client.post("/v1/speech/stt", files={"file": ("a.ogg", b"OggS....", "audio/ogg")}, data={"lang": "hi"})
    assert r.status_code == 503 and r.json()["detail"]["error"] == "speech_not_configured"
    assert app_client.get("/health").json()["speech_enabled"] is False


def test_speech_mock_provider_round_trip(speech_client):
    s = speech_client.get("/v1/speech/status").json()
    assert s["enabled"] and s["provider"] == "mock" and s["tts"] and s["stt"]
    r = speech_client.post("/v1/speech/tts", json={"text": "Namaste", "lang": "hi"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mime"].startswith("audio/") and base64.b64decode(j["audio_base64"])
    r = speech_client.post("/v1/speech/stt", files={"file": ("a.webm", b"\x1aE\xdf\xa3fake", "audio/webm")},
                           data={"lang": "en"})
    assert r.status_code == 200 and isinstance(r.json()["text"], str)
    assert speech_client.post("/v1/speech/tts", json={"text": "", "lang": "hi"}).status_code == 422


def test_placeholder_provider_says_not_implemented(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, SPEECH_ENABLED="true", SPEECH_PROVIDER="bhashini")
    try:
        r = c.post("/v1/speech/tts", json={"text": "Hello", "lang": "hi"})
        assert r.status_code == 503 and r.json()["detail"]["error"] == "speech_provider_not_implemented"
    finally:
        c.__exit__(None, None, None)


def test_whatsapp_voice_note_gets_type_for_now_reply_when_speech_off(app_client):
    wa = WA(app_client, "919811100007")
    wa_start(wa, EN)
    payload = wa_payload(wa.number, "", "wamid.VOICE1")
    msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    msg.pop("text")
    msg["type"] = "audio"
    msg["audio"] = {"id": "media123", "mime_type": "audio/ogg; codecs=opus", "voice": True}
    before = len(app_client.graph.wa_messages(wa.number))
    assert app_client.post("/whatsapp/webhook", json=payload).status_code == 200
    new = app_client.graph.wa_messages(wa.number)[before:]
    assert new and "Voice notes are coming soon" in app_client.graph.as_text(new[-1])


def test_speech_has_a_per_ip_limit(speech_client, monkeypatch):
    from app.speech import api as sp
    sp._CALLS.clear()
    monkeypatch.setenv("SPEECH_RATE_LIMIT", "3")
    codes = [speech_client.post("/v1/speech/tts", json={"text": "Hi", "lang": "en"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    sp._CALLS.clear()


def test_documents_nudge_and_profile_refresh(app_client):
    sh, me = _saved_student(app_client, "9811100008")
    sid0 = me["saved"][0]["scheme_id"]
    r = app_client.patch(f"/v1/companion/me/schemes/{sid0}", json={"status": "docs"}, headers=sh).json()
    assert any(u["kind"] == "docs_nudge" and u["scheme_id"] == sid0 for u in r["me"]["upcoming"])
    # the same number answers again on WhatsApp (e.g. now in PG) -> saved profile follows
    wa = app_client.wa
    wa_start(wa, EN)
    wa_answers(wa, edu="5", state="Rajasthan")
    after = app_client.get("/v1/companion/me", headers=sh).json()
    assert after["answers"]["state"] == "Rajasthan" and after["answers"] != me["answers"]
