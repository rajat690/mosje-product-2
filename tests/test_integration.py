import io
import json

import openpyxl

from conftest import ADMIN_KEY, KEY_RAJAT, KEY_TEAMB, WA, H, sign

REF = {"external_ref": "STU-001", "mobile": "9876500001", "name": "aarav sharma", "state": "Rajasthan",
       "class": "X", "category": "SC", "gender": "M", "income": "1.8 lakh", "reason": "PROBABLE"}


def post(client, key, items, **extra):
    return client.post("/v1/referrals", json={"referrals": items, **extra}, headers=H(key))


def test_auth_errors(client):
    assert client.post("/v1/referrals", json={"referrals": []}).status_code == 401
    r = client.post("/v1/referrals", json={"referrals": []}, headers=H("wrong"))
    assert r.status_code == 401 and r.json()["detail"]["error"] == "invalid_api_key"


def test_batch_create_update_reject(client):
    r = post(client, KEY_RAJAT, [REF, {"name": "no ref"}, {"external_ref": "STU-002", "mobile": "123"},
                                 {"external_ref": "STU-003", "category": "weird"}]).json()
    assert r["created"] == 2 and r["rejected_count"] == 2
    assert {x["index"] for x in r["rejected"]} == {1, 2}
    assert any("category" in w for x in r["warnings"] for w in x["warnings"])
    r2 = post(client, KEY_RAJAT, [{"external_ref": "STU-001", "state": "Gujarat"}]).json()
    assert r2["updated"] == 1
    got = client.get("/v1/referrals/STU-001", headers=H(KEY_RAJAT)).json()
    assert got["known_facts"]["state"] == "Gujarat" and got["known_facts"]["category"] == "SC"
    assert got["known_facts"]["annual_family_income"] == 180000
    assert got["mobile_masked"] == "91••••••0001" and got["status"] == "RECEIVED"


def test_tenant_isolation(client):
    post(client, KEY_RAJAT, [REF])
    assert client.get("/v1/referrals/STU-001", headers=H(KEY_TEAMB)).status_code == 404
    r = client.get("/v1/referrals/STU-001", headers=H(KEY_TEAMB), params={"source_system": "p1-rajat"})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "forbidden_source_system"
    bad = post(client, KEY_TEAMB, [dict(REF, source_system="p1-rajat")]).json()
    assert bad["rejected_count"] == 1
    # same external_ref in another tenant is a different referral
    assert post(client, KEY_TEAMB, [REF]).json()["created"] == 1
    # admin must name the source system (default = 'default')
    assert client.get("/v1/referrals/STU-001", headers=H(ADMIN_KEY)).status_code == 404
    assert client.get("/v1/referrals/STU-001", headers=H(ADMIN_KEY), params={"source_system": "p1-teamB"}).status_code == 200


def test_upload_csv_and_xlsx(client):
    csv_text = open("templates/referrals_template.csv", encoding="utf-8").read()
    r = client.post("/v1/referrals/upload", headers=H(KEY_TEAMB),
                    files={"file": ("referrals.csv", csv_text.encode(), "text/csv")}).json()
    assert r["created"] >= 2 and r["rejected_count"] == 0, r
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["external_ref", "mobile", "name", "state", "class_passed", "category", "annual_family_income"])
    ws.append(["X-1", 9876511111, "Priya Meena", "Rajasthan", "XII", "ST", 150000])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/v1/referrals/upload", headers=H(KEY_TEAMB),
                    files={"file": ("r.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert r["created"] == 1
    got = client.get("/v1/referrals/X-1", headers=H(KEY_TEAMB)).json()
    assert got["known_facts"] == {"state": "Rajasthan", "class_passed": "XII", "category": "ST", "annual_family_income": 150000}
    bad = client.post("/v1/referrals/upload", headers=H(KEY_TEAMB), files={"file": ("r.pdf", b"%PDF", "application/pdf")})
    assert bad.status_code == 415


def test_referral_prefill_whatsapp_round_trip_with_callback(client):
    put = client.put("/v1/source-systems/me", headers=H(KEY_RAJAT),
                     json={"callback_url": "https://p1.example.org/p2-callback", "callback_secret": "s3cret-s3cret-s3cret"})
    assert put.status_code == 200 and put.json()["callback_secret_set"]
    post(client, KEY_RAJAT, [REF])
    wa = WA(client, "919876500001")
    first = wa.send("hi")
    assert "Namaste Aarav!" in first and "1. English" in first
    confirm = wa.send("1")                         # English
    assert "From your records" in confirm and "Rajasthan" in confirm and "₹1,80,000" in confirm
    assert "you can explore" in wa.send("1")       # facts confirmed -> results straight away
    ref = client.get("/v1/referrals/STU-001", headers=H(KEY_RAJAT)).json()
    assert ref["status"] == "COMPLETED" and ref["latest_result"]["prefill_used"] is True
    assert ref["latest_result"]["suggested_schemes"][0]["name"]
    cb = [r for r in client.graph.requests if r["url"] == "https://p1.example.org/p2-callback"]
    assert len(cb) == 1
    assert cb[0]["headers"]["x-p2-signature"] == sign("s3cret-s3cret-s3cret", cb[0]["raw"])
    assert cb[0]["json"]["event"] == "discovery.result" and cb[0]["json"]["result"]["external_ref"] == "STU-001"
    assert ref["callback_status"].startswith("200")
    # results feed, filtered by tenant and since
    res = client.get("/v1/results", headers=H(KEY_RAJAT)).json()
    assert res["count"] == 1 and res["results"][0]["external_ref"] == "STU-001"
    assert client.get("/v1/results", headers=H(KEY_TEAMB)).json()["count"] == 0
    later = client.get("/v1/results", headers=H(KEY_RAJAT), params={"since": res["next_since"]}).json()
    assert later["count"] == 0
    assert client.get("/v1/results", headers=H(KEY_RAJAT), params={"since": "yesterday"}).status_code == 400


def test_prefill_rejected_asks_all(client):
    post(client, KEY_RAJAT, [REF])
    wa = WA(client, "919876500001")
    wa.send("hi")
    wa.send("2")                                   # Hindi
    assert "कौन सी कक्षा" in wa.send("2")           # "No, let me answer"


def test_invite(client):
    post(client, KEY_RAJAT, [REF])
    r = client.post("/v1/referrals/STU-001/invite", headers=H(KEY_RAJAT)).json()
    assert r["status"] == "INVITED" and r["message_id"]
    tpl = client.graph.requests[-1]["json"]["template"]
    assert tpl["name"] == "hello_world" and "components" not in tpl
    client.post("/v1/referrals/STU-001/invite", headers=H(KEY_RAJAT),
                json={"template": "scholarship_discovery_invite_en", "language": "en"})
    comps = client.graph.requests[-1]["json"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in comps] == ["Aarav", "X"]


def test_discover_and_meta(client):
    d = client.post("/v1/discover", headers=H(KEY_TEAMB),
                    json={"state": "Rajasthan", "class_passed": "X", "category": "SC", "gender": "Male",
                          "annual_family_income": 180000, "limit": 3}).json()
    assert d["eligible_count"] > 3 and len(d["schemes"]) == 3
    m = client.get("/v1/meta", headers=H(KEY_TEAMB)).json()
    assert m["schemes_total"] == 547 and "Rajasthan" in m["states"]
