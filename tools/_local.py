"""Helpers to run the app locally in-process with a temporary SQLite DB and a fake WhatsApp API."""
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEMO_ENV = {
    "DATABASE_URL": f"sqlite:///{tempfile.mkdtemp()}/p2_demo.db",
    "P2_API_KEY": "demo-admin-key",
    "P2_API_KEYS": "p1-rajat:demo-key-rajat,p1-teamB:demo-key-teamb",
    "WHATSAPP_VERIFY_TOKEN": "demo-verify",
    "WHATSAPP_TOKEN": "demo-token",
    "WHATSAPP_PHONE_NUMBER_ID": "100000000000001",
    "ELIGIBILITY_AS_OF": "2026-09-28",
    "PUBLIC_BASE_URL": "https://mosje-p2-api.onrender.com",
    "WHATSAPP_DISPLAY_NUMBER": "15550001234",
}


class FakeMeta:
    def __init__(self):
        self.sent, self.callbacks, self.n = [], [], 0

    def handler(self, req: httpx.Request):
        body = json.loads(req.content or b"{}")
        if "graph.facebook.com" in str(req.url):
            self.n += 1
            self.sent.append(body)
            return httpx.Response(200, json={"messages": [{"id": f"wamid.OUT{self.n}"}]})
        self.callbacks.append({"url": str(req.url), "headers": dict(req.headers), "json": body})
        return httpx.Response(200, json={"ok": True})


def start():
    os.environ.update(DEMO_ENV)
    from fastapi.testclient import TestClient
    from app import config, results
    config.reload_settings()
    from app.main import app
    fake = FakeMeta()
    results.TEST_TRANSPORT = httpx.MockTransport(fake.handler)
    c = TestClient(app)
    c.__enter__()
    return c, fake


def wa_in(frm, text, mid):
    """Inbound text message; 'tap:<id>' simulates tapping a reply button / list row with that id."""
    if text.startswith("tap:"):
        msg = {"from": frm, "id": mid, "timestamp": "1790000000", "type": "interactive",
               "interactive": {"type": "list_reply", "list_reply": {"id": text[4:], "title": text[4:]}}}
    else:
        msg = {"from": frm, "id": mid, "timestamp": "1790000000", "type": "text", "text": {"body": text}}
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": DEMO_ENV["WHATSAPP_PHONE_NUMBER_ID"]},
        "messages": [msg]}}]}]}


def show_wa(m: dict) -> str:
    """Readable rendering of an outbound WhatsApp message (text or interactive buttons/list)."""
    if m.get("type") == "text":
        return m["text"]["body"]
    it = m.get("interactive") or {}
    out = [it.get("body", {}).get("text", ""), ""]
    act = it.get("action") or {}
    if it.get("type") == "button":
        out.append("   ".join(f"[ {b['reply']['title']} ]" for b in act.get("buttons", [])))
    else:
        out.append(f"[ ☰ {act.get('button', '')} ]  (list message)")
        for sec in act.get("sections", []):
            out.append(f"  — {sec.get('title', '')} —")
            for r in sec["rows"]:
                out.append(f"  • {r['title']}" + (f"  ({r['description']})" if r.get("description") else "")
                           + f"   ‹id {r['id']}›")
    return "\n".join(out).strip()
