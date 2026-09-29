import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ADMIN_KEY = "admin-test-key-123"
KEY_RAJAT = "rajat-key-abc"
KEY_TEAMB = "teamb-key-xyz"
PHONE_ID = "123456789012345"
APP_SECRET = "app-secret-for-tests"

BASE_ENV = {
    "P2_API_KEY": ADMIN_KEY,
    "P2_API_KEYS": f"p1-rajat:{KEY_RAJAT},p1-teamB:{KEY_TEAMB}",
    "WHATSAPP_VERIFY_TOKEN": "verify-me",
    "WHATSAPP_TOKEN": "EAAG-test-token",
    "WHATSAPP_PHONE_NUMBER_ID": PHONE_ID,
    "WHATSAPP_APP_SECRET": "",
    "COMPANION_PUBLIC": "true",
    "ALLOWED_ORIGINS": "",
    "ELIGIBILITY_AS_OF": "2026-09-27",
}


class GraphMock:
    """Records every outbound HTTP call (Graph API + callbacks) instead of sending it."""

    def __init__(self):
        self.requests = []
        self.fail = False
        self.n = 0

    def handler(self, request: httpx.Request):
        body = json.loads(request.content or b"{}") if request.content else {}
        self.requests.append({"url": str(request.url), "headers": dict(request.headers), "json": body,
                              "raw": request.content})
        if "graph.facebook.com" in str(request.url):
            if self.fail:
                return httpx.Response(401, json={"error": {"code": 190, "message": "Invalid OAuth access token"}})
            self.n += 1
            return httpx.Response(200, json={"messaging_product": "whatsapp",
                                             "messages": [{"id": f"wamid.OUT{self.n}"}]})
        return httpx.Response(200, json={"ok": True})

    @staticmethod
    def as_text(j: dict) -> str:
        """Readable text of a text OR interactive message (body + button / row titles)."""
        if j.get("type") == "text":
            return j["text"]["body"]
        it = j.get("interactive") or {}
        parts = [it.get("body", {}).get("text", "")]
        act = it.get("action") or {}
        for b in act.get("buttons", []):
            parts.append(b["reply"]["title"])
        for sec in act.get("sections", []):
            for r in sec["rows"]:
                parts.append(r["title"] + (" " + r["description"] if r.get("description") else ""))
        return "\n".join(parts)

    def wa_messages(self, to=None):
        return [r["json"] for r in self.requests
                if "graph.facebook.com" in r["url"] and r["json"].get("type") in ("text", "interactive")
                and (to is None or r["json"]["to"] == to)]

    def graph_texts(self, to=None):
        return [self.as_text(j) for j in self.wa_messages(to)]

    def last_text(self, to=None):
        t = self.graph_texts(to)
        return t[-1] if t else None


def make_client(tmp_path, monkeypatch, **env):
    from fastapi.testclient import TestClient
    # Set P2_TEST_DATABASE_URL=postgresql://... to run the whole suite against Postgres.
    db_url = os.environ.get("P2_TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/p2_test.db"
    for k, v in {**BASE_ENV, "DATABASE_URL": db_url, **env}.items():
        monkeypatch.setenv(k, v)
    from app import config, results
    config.reload_settings()
    if os.environ.get("P2_TEST_DATABASE_URL"):
        from app import db as dbm
        dbm.init_engine(db_url)
        dbm.Base.metadata.drop_all(dbm.engine)
        dbm.engine.dispose()
    from app.main import app
    mock = GraphMock()
    results.TEST_TRANSPORT = httpx.MockTransport(mock.handler)
    client = TestClient(app)
    client.__enter__()
    client.graph = mock
    return client


@pytest.fixture
def client(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    yield c
    c.__exit__(None, None, None)
    from app import results
    results.TEST_TRANSPORT = None


def wa_payload(frm: str, text: str, mid: str, kind: str = "text") -> dict:
    msg = {"from": frm, "id": mid, "timestamp": "1790000000", "type": kind}
    if kind == "text":
        msg["text"] = {"body": text}
    elif kind == "button":
        msg["button"] = {"text": text, "payload": text}
    elif kind == "image":
        msg["image"] = {"id": "img1", "mime_type": "image/jpeg"}
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "15550000000", "phone_number_id": PHONE_ID},
                "contacts": [{"profile": {"name": "Test"}, "wa_id": frm}],
                "messages": [msg]}}]}]}


class WA:
    """Helper to chat with the bot over the (mocked) WhatsApp webhook."""

    def __init__(self, client, number="919876543210"):
        self.c, self.number, self.i, self.last = client, number, 0, []

    def send(self, text, kind="text"):
        """Send one inbound message; returns the text of ALL messages the bot sent back (joined)."""
        self.i += 1
        before = len(self.c.graph.wa_messages(self.number))
        r = self.c.post("/whatsapp/webhook", json=wa_payload(self.number, text, f"wamid.IN{self.number}{self.i}", kind))
        assert r.status_code == 200, r.text
        new = self.c.graph.wa_messages(self.number)[before:]
        self.last = new
        return "\n\n".join(self.c.graph.as_text(j) for j in new) if new else None

    def tap(self, reply_id, title=""):
        """Simulate tapping a reply button / list row (interactive reply carrying the option id)."""
        self.i += 1
        before = len(self.c.graph.wa_messages(self.number))
        payload = wa_payload(self.number, "", f"wamid.IN{self.number}{self.i}")
        msg = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        msg.pop("text")
        msg["type"] = "interactive"
        msg["interactive"] = {"type": "list_reply", "list_reply": {"id": reply_id, "title": title or reply_id}}
        r = self.c.post("/whatsapp/webhook", json=payload)
        assert r.status_code == 200, r.text
        new = self.c.graph.wa_messages(self.number)[before:]
        self.last = new
        return "\n\n".join(self.c.graph.as_text(j) for j in new) if new else None


def sign(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def H(key):
    return {"X-API-Key": key}


# ---- flow helpers: language (alphabetical list: English = 4) -> consent -> 5 questions (State first) -> summary
EN = "4"
HI = "6"
BN = "2"


def wa_start(wa, lang=EN, greet="hi"):
    """Greeting -> language -> Agree. Returns the text of the first question."""
    wa.send(greet)
    wa.send(lang)
    return wa.send("1")                       # Agree


def wa_answers(wa, edu="4", gender="1", income="1", category="4", state="Karnataka", proceed=True):
    """Answer the 5 questions (Update 2 order: State, education level, gender, monthly income band, category)
    and Proceed."""
    for m in (state, edu, gender, income):
        wa.send(m)
    out = wa.send(category)
    return wa.send("1") if proceed else out
