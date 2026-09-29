from urllib.parse import parse_qs, urlparse

from conftest import ADMIN_KEY, KEY_RAJAT, KEY_TEAMB, WA, H, make_client

REF = {"external_ref": "STU-001", "mobile": "9876500001", "name": "Aarav Sharma", "state": "Rajasthan",
       "class_passed": "X", "category": "SC", "gender": "Male", "annual_family_income": 180000}


def register(client, key=KEY_RAJAT, **over):
    body = {"message_id": "wave1-msg1", "campaign": "PROBABLE wave 1", "channel": "sms",
            "template_text": "Namaste {{1}}, find scholarships: {{link}}", "template_version": "v1",
            "sent_at": "2026-10-01T09:30:00+05:30", **over}
    r = client.post("/v1/outreach-messages", json=body, headers=H(key))
    assert r.status_code == 201, r.text
    return r.json()


def result_for(client, key, **params):
    res = client.get("/v1/results", headers=H(key), params=params).json()["results"]
    return res


def finish_flow(wa_or_chat):
    for m in ["1", "1", "Rajasthan", "1", "2"]:
        wa_or_chat(m)
    return wa_or_chat("180000")


# ------------------------------------------------------------------ OUTREACH
def test_outreach_registry_and_links(client):
    client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [REF]})
    om = register(client, recipients=["STU-001", "NOT-A-REFERRAL"])
    assert om["code"].startswith("OM-") and om["source_system"] == "p1-rajat"
    assert om["sent_at"].startswith("2026-10-01T04:00:00")          # stored in UTC
    recs = {r["recipient_ref"]: r for r in om["recipients"]}
    assert recs["STU-001"]["referral_linked"] and not recs["NOT-A-REFERRAL"]["referral_linked"]
    q = parse_qs(urlparse(recs["STU-001"]["web_link"]).query)
    assert q["src"] == ["outreach"] and q["om"] == [om["code"]] and q["r"] == [recs["STU-001"]["code"]]
    assert "STU-001" not in recs["STU-001"]["web_link"]              # links carry opaque codes, not refs
    assert f"{om['code']}-{recs['STU-001']['code']}" in recs["STU-001"]["whatsapp_text"]
    assert om["whatsapp_number_known"] is False and om["links"]["whatsapp_link"] is None
    # re-register = update, same code
    again = register(client, campaign="renamed")
    assert again["code"] == om["code"] and again["campaign"] == "renamed"
    # tenant isolation
    assert client.get("/v1/outreach-messages/wave1-msg1", headers=H(KEY_TEAMB)).status_code == 404
    assert client.get("/v1/outreach-messages", headers=H(KEY_TEAMB)).json()["count"] == 0


def test_outreach_whatsapp_per_recipient_link(client):
    client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [dict(REF, mobile="9876599999")]})
    om = register(client, recipients=["STU-001"])
    text = om["recipients"][0]["whatsapp_text"]
    wa = WA(client, "919876500001")                   # different phone than the referral's
    first = wa.send(text)
    assert "Namaste Aarav!" in first                  # recipient code linked the referral
    wa.send("1")
    wa.send("1")                                      # confirm pre-filled facts -> results
    r = result_for(client, KEY_RAJAT, entry_source="OUTREACH")
    assert len(r) == 1
    e = r[0]["entry"]
    assert e["source"] == "OUTREACH" and e["channel"] == "whatsapp"
    assert e["outreach_message_id"] == "wave1-msg1" and e["campaign"] == "PROBABLE wave 1"
    assert e["recipient_ref"] == "STU-001" and e["first_touch"]["raw_text"] == text and e["first_touch_at"]
    assert r[0]["external_ref"] == "STU-001" and r[0]["status"] == "COMPLETED"
    stats = client.get("/v1/outreach-messages/wave1-msg1", headers=H(KEY_RAJAT)).json()["stats"]
    assert stats["sessions_started"] == 1 and stats["sessions_completed"] == 1 and stats["by_channel"]["whatsapp"] == 1


def test_outreach_whatsapp_generic_code_and_code_restarts_journey(client):
    om = register(client)
    wa = WA(client, "919811111111")
    wa.send("hi")                                     # organic first
    wa.send("1")
    assert "Namaste" in wa.send(om["links"]["whatsapp_text"])   # code mid-journey -> fresh attributed session
    r = result_for(client, KEY_RAJAT)
    assert len(r) == 1 and r[0]["entry"]["source"] == "OUTREACH" and r[0]["external_ref"] is None
    walkin = result_for(client, ADMIN_KEY, source_system="walk-in")
    assert walkin[0]["entry"]["source"] == "ORGANIC" and walkin[0]["status"] == "RESTARTED"


def test_outreach_unknown_code_still_outreach(client):
    WA(client, "919822222222").send("Hi, code OM-ZZZZZZ")
    r = result_for(client, ADMIN_KEY, source_system="walk-in")
    assert r[0]["entry"]["source"] == "OUTREACH" and r[0]["entry"]["first_touch"]["resolved"] is False


def test_outreach_web_links(client):
    client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [REF]})
    om = register(client, recipients=["STU-001"])
    rc = om["recipients"][0]["code"]
    d = client.post("/v1/chat/sessions", json={"entry": {"src": "outreach", "om": om["code"], "r": rc,
                                                         "utm_source": "p1-rajat"}}).json()
    assert d["entry_source"] == "OUTREACH" and d["source_system"] == "p1-rajat" and "Namaste Aarav" in d["reply"]["text"]
    # om may also be the Product 1 message_id; utm_campaign alone also works
    d2 = client.post("/v1/chat/sessions", json={"entry": {"src": "outreach", "om": "wave1-msg1"}}).json()
    d3 = client.post("/v1/chat/sessions", json={"entry": {"utm_campaign": om["code"], "utm_medium": "sms"}}).json()
    assert d2["entry_source"] == d3["entry_source"] == "OUTREACH"
    r = result_for(client, KEY_RAJAT, channel="web", entry_source="OUTREACH")
    assert len(r) == 3 and {x["entry"]["outreach_message_id"] for x in r} == {"wave1-msg1"}
    assert r[0]["entry"]["recipient_ref"] == "STU-001" and r[0]["entry"]["first_touch"]["params"]["utm_source"] == "p1-rajat"
    assert client.get("/v1/outreach-messages/wave1-msg1", headers=H(KEY_RAJAT)).json()["stats"]["by_channel"]["web"] == 3


# ------------------------------------------------------------------ ORGANIC
def test_organic_both_channels(client):
    WA(client, "919833333333").send("hello")
    d = client.post("/v1/chat/sessions", json={"entry": {"utm_source": "google"}}).json()
    assert d["entry_source"] == "ORGANIC"
    r = result_for(client, ADMIN_KEY, source_system="walk-in", entry_source="ORGANIC")
    assert {x["entry"]["channel"] for x in r} == {"whatsapp", "web"}
    web = next(x for x in r if x["channel"] == "web")
    assert web["entry"]["first_touch"]["params"] == {"utm_source": "google"}


# ------------------------------------------------------------------ PEER_REFERRAL
def test_feedback_share_and_peer_referrals(client):
    wa = WA(client, "919844444444")
    wa.send("hi")
    finish_flow(wa.send)
    assert "How useful" in wa.send("2")               # option 2 = rate & share
    assert "comment" in wa.send("4")
    share_msg = wa.send("Very helpful, thanks")
    assert "https://wa.me/15550000000?text=" in share_msg          # number learned from webhook metadata
    res = result_for(client, ADMIN_KEY, source_system="walk-in")[0]
    code = res["share_code"]
    assert code.startswith("REF-") and code in share_msg and "src=referral&ref=" + code in share_msg
    assert res["feedback"] == {"rating": 4, "comment": "Very helpful, thanks"}
    assert "Rate this service" not in share_msg        # feedback option disappears once given
    # friend 1 on WhatsApp with the share text
    WA(client, "919855555555").send(f"Hi, my friend suggested this scholarship helper. Code {code}")
    # friend 2 on the web share link
    d = client.post("/v1/chat/sessions", json={"entry": {"src": "referral", "ref": code}}).json()
    assert d["entry_source"] == "PEER_REFERRAL"
    all_ = result_for(client, ADMIN_KEY, source_system="walk-in")
    peers = [x for x in all_ if x["entry"]["source"] == "PEER_REFERRAL"]
    assert len(peers) == 2 and {p["entry"]["referrer_share_code"] for p in peers} == {code}
    referrer = next(x for x in all_ if x["share_code"] == code)
    assert referrer["peer_referrals_count"] == 2
    page = client.get("/admin", auth=("admin", ADMIN_KEY)).text
    assert "PEER_REFERRAL" in page and code in page and "Sessions by entry source" in page


def test_rating_values_and_web_share_payload(client):
    d = client.post("/v1/chat/sessions", json={}).json()
    sid, tok = d["session_id"], d["session_token"]
    say = lambda m: client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": m},
                                headers={"X-Session-Token": tok}).json()
    say("1")
    finish_flow(say)
    assert say("2")["reply"]["state"] == "FEEDBACK_RATING"
    assert "did not understand" in say("9")["reply"]["text"]
    assert say("5")["reply"]["state"] == "FEEDBACK_COMMENT"
    out = say("SKIP")["reply"]
    assert out["share"]["share_code"].startswith("REF-") and "src=referral" in out["share"]["web_link"]
    assert out["state"] == "RESULTS"
    r = client.get(f"/v1/chat/sessions/{sid}", headers={"X-Session-Token": tok}).json()["result"]
    assert r["feedback"] == {"rating": 5, "comment": None}


def test_restart_keeps_attribution(client):
    d = client.post("/v1/chat/sessions", json={"entry": {"src": "referral", "ref": "REF-UNKNWN"}}).json()
    new = client.post(f"/v1/chat/sessions/{d['session_id']}/messages", json={"text": "restart"},
                      headers={"X-Session-Token": d["session_token"]}).json()
    assert new["new_session"] and new["entry_source"] == "PEER_REFERRAL"


def test_display_number_from_env(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, WHATSAPP_DISPLAY_NUMBER="+1 555 123 4567")
    try:
        om = register(c)
        assert om["links"]["whatsapp_link"].startswith("https://wa.me/15551234567?text=Hi%2C%20I%20want")
    finally:
        c.__exit__(None, None, None)
