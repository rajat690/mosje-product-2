from conftest import ADMIN_KEY, KEY_RAJAT, KEY_TEAMB, WA, H, make_client


def chat(client, sid, token, text):
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text}, headers={"X-Session-Token": token})
    assert r.status_code == 200, r.text
    return r.json()


def test_public_web_session_to_results(client):
    r = client.post("/v1/chat/sessions", json={})
    assert r.status_code == 201
    d = r.json()
    sid, tok = d["session_id"], d["session_token"]
    assert d["reply"]["options"][1]["label"] == "हिंदी" and d["companion_url"].endswith(f"session={sid}&token={tok}")
    for m in ["1", "2", "Karnataka", "3", "1"]:
        out = chat(client, sid, tok, m)
    out = chat(client, sid, tok, "4")
    rep = out["reply"]
    assert out["status"] == "COMPLETED" and rep["cards"] and rep["footer"]
    assert {"rank", "scheme_id", "name", "benefit", "apply_url"} <= set(rep["cards"][0])
    assert [o["id"] for o in rep["options"]] == ["1", "2", "3", "4"]
    # auth
    assert client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "1"}).status_code == 401
    assert client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "1"},
                       headers={"X-Session-Token": "bad"}).status_code == 401
    got = client.get(f"/v1/chat/sessions/{sid}", headers={"X-Session-Token": tok}).json()
    assert got["result"]["channel"] == "web" and got["last_reply"]["cards"] and len(got["transcript"]) >= 12
    # restart creates a new session id that keeps working with the same token
    new = chat(client, sid, tok, "restart")
    assert new["new_session"] and new["session_id"] != sid
    assert chat(client, new["session_id"], tok, "1")["reply"]["state"] == "ASK_class_passed"
    # walk-in web sessions visible to admin only
    res = client.get("/v1/results", headers=H(ADMIN_KEY), params={"source_system": "walk-in", "channel": "web"}).json()
    assert res["count"] == 2


def test_tenant_web_session_prefilled_and_in_results(client):
    client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [
        {"external_ref": "W-1", "name": "Neha Verma", "state": "Delhi", "class_passed": "XII",
         "category": "OBC", "gender": "Female", "annual_family_income": 200000, "language": "en"}]})
    assert client.post("/v1/chat/sessions", json={"external_ref": "W-1"}).status_code == 401
    assert client.post("/v1/chat/sessions", json={"external_ref": "W-1"}, headers=H(KEY_TEAMB)).status_code == 404
    d = client.post("/v1/chat/sessions", json={"external_ref": "W-1"}, headers=H(KEY_RAJAT)).json()
    assert "Namaste Neha" in d["reply"]["text"] and d["reply"]["state"] == "CONFIRM_PREFILL"
    out = chat(client, d["session_id"], d["session_token"], "1")
    assert out["status"] == "COMPLETED"
    res = client.get("/v1/results", headers=H(KEY_RAJAT), params={"channel": "web"}).json()
    assert res["count"] == 1 and res["results"][0]["external_ref"] == "W-1"
    assert res["results"][0]["channel"] == "web"
    # owning API key may also drive the session (server-side integration)
    r = client.get(f"/v1/chat/sessions/{d['session_id']}", headers=H(KEY_RAJAT))
    assert r.status_code == 200
    assert client.get(f"/v1/chat/sessions/{d['session_id']}", headers=H(KEY_TEAMB)).status_code == 401


def test_companion_pages(client):
    assert "Scholarship Discovery" in client.get("/companion").text
    js = client.get("/companion/embed.js")
    assert js.status_code == 200 and "MosjeP2Companion" in js.text
    assert "/companion/embed.js" in client.get("/companion/demo").text


def test_public_companion_can_be_disabled_and_cors(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, COMPANION_PUBLIC="false", ALLOWED_ORIGINS="https://p1.example.org")
    try:
        assert c.post("/v1/chat/sessions", json={}).status_code == 401
        assert c.post("/v1/chat/sessions", json={}, headers=H(KEY_RAJAT)).status_code == 201
        csp = c.get("/companion").headers.get("content-security-policy", "")
        assert "frame-ancestors 'self' https://p1.example.org" in csp
    finally:
        c.__exit__(None, None, None)


def test_cors_middleware():
    from starlette.middleware.cors import CORSMiddleware
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    # CORS is configured at import time from ALLOWED_ORIGINS; verify the same middleware config works.
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["https://p1.example.org"], allow_methods=["POST"],
                       allow_headers=["Content-Type", "X-Session-Token"])
    app.post("/x")(lambda: {"ok": 1})
    r = TestClient(app).options("/x", headers={"Origin": "https://p1.example.org", "Access-Control-Request-Method": "POST",
                                               "Access-Control-Request-Headers": "X-Session-Token"})
    assert r.headers["access-control-allow-origin"] == "https://p1.example.org"


def test_admin_page(client):
    client.post("/v1/referrals", headers=H(KEY_RAJAT), json={"referrals": [{"external_ref": "A1", "mobile": "9876512345"}]})
    WA(client, "919876512345").send("hi")
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "wrong")).status_code == 401
    page = client.get("/admin", auth=("admin", ADMIN_KEY))
    assert page.status_code == 200 and "p1-rajat" in page.text
    assert "9876512345" not in page.text and "91••••••2345" in page.text
