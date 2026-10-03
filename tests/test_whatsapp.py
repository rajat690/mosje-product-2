import re
import json

from conftest import ADMIN_KEY, APP_SECRET, KEY_RAJAT, PHONE_ID, WA, H, make_client, sign, wa_payload


def test_health_and_docs_without_whatsapp(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, WHATSAPP_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="",
                    WHATSAPP_VERIFY_TOKEN="", P2_API_KEY="", P2_API_KEYS="")
    try:
        h = c.get("/health").json()
        assert h["status"] == "ok" and h["whatsapp_configured"] is False
        assert c.get("/docs").status_code == 200
        # inbound still accepted; reply is logged as not sent (no crash)
        assert c.post("/whatsapp/webhook", json=wa_payload("919000000001", "hi", "wamid.X1")).status_code == 200
        assert c.graph.requests == []
        assert c.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                                  "hub.challenge": "1"}).status_code == 503
        assert c.get("/v1/results", headers=H("anything")).status_code == 503
    finally:
        c.__exit__(None, None, None)


def test_verify_handshake(client):
    ok = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me",
                                                 "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope",
                                                  "hub.challenge": "12345"})
    assert bad.status_code == 403


def test_full_conversation_and_graph_request_format(client):
    wa = WA(client)
    first = wa.send("hi")
    assert "Discovery Assistant" in first and "English" in first and "हिंदी (Hindi)" in first
    lst = wa.last[-1]
    assert lst["type"] == "interactive" and lst["interactive"]["type"] == "list"
    rows = [r for sec in lst["interactive"]["action"]["sections"] for r in sec["rows"]]
    assert len(rows) <= 10 and rows[-1]["id"] == "__pg:2"               # 14 languages -> 2 pages
    req = client.graph.requests[-1]
    assert req["url"] == f"https://graph.facebook.com/v21.0/{PHONE_ID}/messages"
    assert req["headers"]["authorization"] == "Bearer EAAG-test-token"
    assert req["json"]["messaging_product"] == "whatsapp" and req["json"]["to"] == "919876543210"
    consent = wa.send("4")                          # English (alphabetical list: 4th)
    assert "Agree" in consent and "Don't agree" in consent
    assert wa.last[-1]["interactive"]["type"] == "button"
    assert "(1/5) Which state's scholarships would you like to see?" in wa.send("1")
    assert "(2/5) What is your current education level" in wa.send("Rajasthan")
    assert "gender" in wa.send("3")                  # Class 12 passed (more than 5 schemes -> "More schemes")
    assert "monthly" in wa.send("2")                 # Female
    assert "social category" in wa.send("15000")     # typed monthly income -> ₹1,80,000 a year
    summary = wa.send("SC")
    assert "Please check your details" in summary and "Edit details" in summary
    assert [b["reply"]["id"] for b in wa.last[-1]["interactive"]["action"]["buttons"]] == ["proceed", "edit"]
    assert summary.index("State/UT: Rajasthan") < summary.index("Education level")
    final = wa.send("1")                             # Proceed
    assert "scholarship(s) you can explore" in final
    assert "Final eligibility is decided" in final
    # Update 2: compact listing - name · State/Central · Department only
    assert re.search(r"\*1\. [^*\n]+ · (Central|Rajasthan)", final)   # compact card line
    assert "Eligibility:" not in final and "Required documents:" not in final and "Application:" not in final
    more = wa.tap("more")
    assert "showing 6–" in more
    # Update 3 (Product Vision s.9): the student's own State schemes are listed first
    assert re.search(r"\*1\. [^*\n]+ · Rajasthan", final)
    more2 = wa.tap("more")
    more3 = wa.tap("more")
    assert "Post-Matric Scholarship for SC Students" in final + more + more2 + more3
    r = client.get("/v1/results", headers=H(ADMIN_KEY), params={"source_system": "walk-in"}).json()
    assert r["count"] == 1 and r["results"][0]["status"] == "COMPLETED" and r["results"][0]["channel"] == "whatsapp"
    assert r["results"][0]["answers"]["annual_family_income"] == 180000
    assert r["results"][0]["mobile_masked"].endswith("3210") and "9876543210" not in json.dumps(r)


def test_idempotent_on_message_id(client):
    p = wa_payload("919111111111", "hi", "wamid.DUP")
    client.post("/whatsapp/webhook", json=p)
    client.post("/whatsapp/webhook", json=p)
    assert len(client.graph.graph_texts("919111111111")) == 1


def test_signature_checked_when_app_secret_set(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, WHATSAPP_APP_SECRET=APP_SECRET)
    try:
        raw = json.dumps(wa_payload("919222222222", "hi", "wamid.S1")).encode()
        assert c.post("/whatsapp/webhook", content=raw, headers={"Content-Type": "application/json"}).status_code == 401
        assert c.post("/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": "sha256=bad"}).status_code == 401
        ok = c.post("/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": sign(APP_SECRET, raw)})
        assert ok.status_code == 200 and ok.json()["queued"] == 1
    finally:
        c.__exit__(None, None, None)


def test_status_updates_recorded(client):
    WA(client, "919333333333").send("hi")
    status = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "statuses": [{"id": "wamid.OUT1", "status": "read", "recipient_id": "919333333333"}]}}]}]}
    assert client.post("/whatsapp/webhook", json=status).status_code == 200
    from app import db as dbm
    from app.db import Message
    s = dbm.SessionLocal()
    assert s.query(Message).filter_by(external_id="wamid.OUT1").one().status == "read"
    s.close()


def test_non_text_and_button_messages(client):
    wa = WA(client, "919444444444")
    assert "reply with text" in wa.send("", kind="image")
    assert "Discovery Assistant" in wa.send("Find scholarships for me", kind="button")


def test_graph_error_does_not_crash(client):
    client.graph.fail = True
    WA(client, "919555555555").send("hi")
    from app import db as dbm
    from app.db import Message
    s = dbm.SessionLocal()
    out = s.query(Message).filter_by(direction="out").all()
    assert out and out[-1].status.startswith("failed: HTTP 401")
    s.close()


def test_send_template_admin_only(client):
    body = {"to": "9876543210"}
    assert client.post("/whatsapp/send-template", json=body).status_code == 401
    assert client.post("/whatsapp/send-template", json=body, headers=H(KEY_RAJAT)).status_code == 403
    r = client.post("/whatsapp/send-template", json=body, headers=H(ADMIN_KEY)).json()
    assert r["status"] == "accepted"
    sent = client.graph.requests[-1]["json"]
    assert sent["type"] == "template" and sent["template"]["name"] == "hello_world"
    assert sent["template"]["language"]["code"] == "en_US" and sent["to"] == "919876543210"
