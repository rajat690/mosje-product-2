"""WhatsApp channel adapter (Meta WhatsApp Cloud API).

GET  /whatsapp/webhook        Meta verification handshake
POST /whatsapp/webhook        inbound messages + delivery statuses (200 returned fast, work done in background)
POST /whatsapp/send-template  admin-key protected test sender (hello_world)

Replies are sent as WhatsApp *interactive* messages (update 1):
  * up to 3 options with short labels  -> reply buttons (title <= 20 chars)
  * up to 10 options                    -> list message (row title <= 24, description <= 72)
  * more than 10 (States, languages)    -> paginated list; the "More options" row id is __pg:<n>,
                                           answered here from the stored last reply (no bot step)
  * body longer than 1024 characters    -> the text is sent first, then a short interactive message
Set WHATSAPP_INTERACTIVE=false to fall back to plain numbered text.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import attribution as A
from .. import db as dbm
from .. import results
from ..config import settings
from ..conversation import core
from ..conversation.texts import t
from ..db import Message, ProcessedEvent
from ..facts import norm_mobile
from ..security import Caller, require_admin, require_api_key

log = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ------------------------------------------------------------------ Graph API client
def graph_url() -> str:
    return f"{settings.graph_base}/{settings.graph_version}/{settings.wa_phone_number_id}/messages"


def graph_send(payload: dict) -> tuple[str, Optional[str]]:
    """POST to the Graph API. Returns (status, message_id). Never raises."""
    if not settings.whatsapp_configured:
        return "not_sent: WhatsApp not configured (WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID)", None
    try:
        with results.http_client(timeout=15.0) as c:
            r = c.post(graph_url(), json=payload,
                       headers={"Authorization": f"Bearer {settings.wa_token}"})
        if r.status_code >= 400:
            try:
                err = r.json().get("error", {})
                msg = f"{err.get('code')} {err.get('message', '')}"
            except Exception:  # noqa: BLE001
                msg = r.text[:150]
            log.warning("Graph API error %s: %s", r.status_code, msg)
            return f"failed: HTTP {r.status_code} {msg}"[:200], None
        mid = (r.json().get("messages") or [{}])[0].get("id")
        return "accepted", mid
    except Exception as e:  # noqa: BLE001
        log.warning("Graph API call failed: %s", e)
        return f"failed: {type(e).__name__}", None


def send_text(to: str, body: str) -> tuple[str, Optional[str]]:
    return graph_send({"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                       "type": "text", "text": {"preview_url": False, "body": body}})


def send_template(to: str, name: str, lang: str, params: list[str] | None = None) -> tuple[str, Optional[str]]:
    tpl = {"name": name, "language": {"code": lang}}
    if params:
        tpl["components"] = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]
    return graph_send({"messaging_product": "whatsapp", "to": to, "type": "template", "template": tpl})


# ------------------------------------------------------------------ webhook verification
@router.get("/webhook", response_class=PlainTextResponse)
def verify(hub_mode: str = Query(None, alias="hub.mode"),
           hub_verify_token: str = Query(None, alias="hub.verify_token"),
           hub_challenge: str = Query(None, alias="hub.challenge")):
    if not settings.verify_token:
        raise HTTPException(503, "WHATSAPP_VERIFY_TOKEN is not set on the server")
    if hub_mode == "subscribe" and hub_verify_token and hmac.compare_digest(hub_verify_token, settings.verify_token):
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(403, "Verification failed")


def signature_ok(raw: bytes, header: Optional[str]) -> bool:
    if not settings.wa_app_secret:
        return True                     # signature check is optional (enable by setting WHATSAPP_APP_SECRET)
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.wa_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def extract_text(msg: dict) -> Optional[str]:
    typ = msg.get("type")
    if typ == "text":
        return (msg.get("text") or {}).get("body", "")
    if typ == "button":
        return (msg.get("button") or {}).get("text") or (msg.get("button") or {}).get("payload")
    if typ == "interactive":
        it = msg.get("interactive") or {}
        rep = it.get("button_reply") or it.get("list_reply") or {}
        return rep.get("id") or rep.get("title")
    return None


UNSUPPORTED = "Please reply with text (a number or a word). / कृपया टेक्स्ट में जवाब दें।"

# ------------------------------------------------------------------ interactive message builder
BODY_MAX, BTN_TITLE, ROW_TITLE, ROW_DESC, SECTION_TITLE, LIST_BUTTON, MAX_ROWS = 1024, 20, 24, 72, 24, 20, 10
PAGE_PREFIX = "__pg:"


def clip(s: str, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _text_payload(body: str) -> dict:
    return {"type": "text", "text": {"preview_url": False, "body": body[:4096]}}


def _pages(items: list, navs: list) -> list[list]:
    if len(items) + len(navs) <= MAX_ROWS:
        return [items]
    first = MAX_ROWS - len(navs) - 1                 # page 1: items + navs + "more"
    later = MAX_ROWS - len(navs) - 2                 # other pages: items + navs + "previous" + "more"
    pages, rest = [items[:first]], items[first:]
    while rest:
        cap = later if len(rest) > later + 1 else later + 1   # last page has no "more" row
        pages.append(rest[:cap])
        rest = rest[cap:]
    return pages


def build_messages(reply: "core.BotReply", page: int = 1) -> list[dict]:
    """BotReply -> list of Cloud API message payloads (without 'to')."""
    lang = reply.language
    opts = reply.options or []
    if not settings.wa_interactive or not opts:
        return [_text_payload(core.render_text(reply))]
    body = core.render_text(reply, limit=4096, with_options=False)
    out = []
    if reply.share and reply.share.get("message"):
        # the ready-made share message goes alone, so the student can long-press > Forward it as-is
        out.append(_text_payload(reply.share["message"]))
        body = t(lang, "share_fwd_hint")
    if (reply.view or "").startswith("DETAIL"):
        # Update 2: the detail card has exactly 3 buttons (no Main menu button) - MENU can still be typed
        body = (body + "\n\n" if body else "") + t(lang, "menu_hint")
    fits = lambda xs: len(xs) <= 3 and all(len(o["label"]) <= BTN_TITLE for o in xs)
    if not fits(opts) and any(o.get("optional") for o in opts) and fits([o for o in opts if not o.get("optional")]):
        # e.g. Go Back / Share Scheme / Share Feedback + Main Menu: keep 3 buttons, MENU stays available by typing
        opts = [o for o in opts if not o.get("optional")]
        body = (body + "\n\n" if body else "") + t(lang, "menu_hint")
    if fits(opts):
        if len(body) > BODY_MAX:
            out.append(_text_payload(body))
            body = t(lang, "choose_next")
        out.append({"type": "interactive", "interactive": {
            "type": "button", "body": {"text": body or t(lang, "choose_next")},
            "action": {"buttons": [{"type": "reply", "reply": {"id": str(o["id"])[:256], "title": clip(o["label"], BTN_TITLE)}}
                                   for o in opts]}}})
        return out
    items = [o for o in opts if o.get("kind", "item") == "item"]
    navs = [o for o in opts if o.get("kind") == "nav"]
    pages = _pages(items, navs)
    n = len(pages)
    page = max(1, min(page, n))
    rows = [{"id": str(o["id"])[:200], "title": clip(o["label"], ROW_TITLE),
             **({"description": clip(o.get("desc") or (o["label"] if len(o["label"]) > ROW_TITLE else ""), ROW_DESC)}
                if (o.get("desc") or len(o["label"]) > ROW_TITLE) else {})}
            for o in pages[page - 1]]
    pager = []
    if page > 1:
        pager.append({"id": f"{PAGE_PREFIX}{page - 1}", "title": clip(t(lang, "wa_prev"), ROW_TITLE)})
    if page < n:
        pager.append({"id": f"{PAGE_PREFIX}{page + 1}", "title": clip(t(lang, "wa_next"), ROW_TITLE),
                      "description": f"{page + 1}/{n}"})
    sections = [{"title": clip(t(lang, "wa_options"), SECTION_TITLE), "rows": rows + pager}] if rows + pager else []
    if navs:
        sections.append({"title": clip(t(lang, "wa_nav"), SECTION_TITLE),
                         "rows": [{"id": str(o["id"]), "title": clip(o["label"], ROW_TITLE)} for o in navs]})
    if page > 1:
        body = t(lang, "wa_page", p=page, n=n)
    elif len(body) > BODY_MAX:
        out.append(_text_payload(body))
        body = t(lang, "choose_next") if n == 1 else t(lang, "wa_page", p=1, n=n)
    out.append({"type": "interactive", "interactive": {
        "type": "list", "body": {"text": body or t(lang, "choose_next")},
        "action": {"button": clip(t(lang, "wa_choose"), LIST_BUTTON), "sections": sections}}})
    return out


def payload_text(p: dict) -> str:
    """Readable copy of an outbound payload for the message log / admin page."""
    if p.get("type") == "text":
        return p["text"]["body"]
    it = p.get("interactive", {})
    lines = [it.get("body", {}).get("text", "")]
    if it.get("type") == "button":
        lines.append(" | ".join(f"[{b['reply']['title']}]" for b in it["action"]["buttons"]))
    else:
        for sec in it.get("action", {}).get("sections", []):
            lines.append(" | ".join(f"[{r['title']}]" for r in sec["rows"]))
    return "\n".join(x for x in lines if x)


def send_reply(db, s, to: str, reply: "core.BotReply", page: int = 1) -> None:
    for p in build_messages(reply, page):
        st, mid = graph_send({"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **p})
        core.log_message(db, s, "out", payload_text(p), channel="whatsapp", external_id=mid, status=st)


# ------------------------------------------------------------------ inbound processing (background)
def process_inbound(wa_id: str, msg_id: str, text: Optional[str]) -> None:
    db = dbm.SessionLocal()
    callbacks = []
    try:
        s = core.latest_session_for_wa(db, wa_id)
        if text is None:
            core.log_message(db, s, "in", "[non-text message]", channel="whatsapp", external_id=msg_id)
            msg = t(s.language, "unsupported") if s is not None and s.language != "en" else UNSUPPORTED
            st, mid = send_text(wa_id, msg)
            core.log_message(db, s, "out", msg, channel="whatsapp", external_id=mid, status=st)
            db.commit()
            return
        if text.startswith(PAGE_PREFIX) and s is not None and s.last_reply:
            core.log_message(db, s, "in", text, channel="whatsapp", external_id=msg_id)
            try:
                page = int(text[len(PAGE_PREFIX):])
            except ValueError:
                page = 1
            fields_ = core.BotReply.__dataclass_fields__
            send_reply(db, s, wa_id, core.BotReply(**{k: v for k, v in s.last_reply.items() if k in fields_}), page)
            db.commit()
            return
        attr = A.from_whatsapp_text(db, text)
        if attr.has_code or s is None or (s.status == "OPTED_OUT" and core.is_greeting(text)):
            # a code (clicked outreach / share link) always starts a fresh, attributed journey
            if s is not None and s.status == "ACTIVE":
                s.status = "RESTARTED"
            ref = attr.referral or core.find_referral_for_mobile(
                db, wa_id, attr.outreach.source_system if attr.outreach else None)
            prev = s or core.latest_session_for_wa(db, wa_id, include_restarted=True)
            s, reply = core.start_session(db, channel="whatsapp", wa_id=wa_id, referral=ref, attribution=attr,
                                          language=core.chosen_language(prev))
            core.log_message(db, s, "in", text, channel="whatsapp", external_id=msg_id)
        else:
            core.log_message(db, s, "in", text, channel="whatsapp", external_id=msg_id)
            s, reply = core.handle_message(db, s, text)
        if "completed" in reply.events or "opted_out" in reply.events:
            callbacks.append(s.id)
        db.commit()
        if not reply.silent:
            s.last_reply = reply.to_dict()
            send_reply(db, s, wa_id, reply)
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("Failed to process inbound WhatsApp message %s", msg_id)
    finally:
        db.close()
    for sid in callbacks:
        results.push_callback(sid)


def process_status(msg_id: str, status: str, errors: list | None) -> None:
    db = dbm.SessionLocal()
    try:
        m = db.execute(select(Message).where(Message.external_id == msg_id)).scalar_one_or_none()
        if m:
            m.status = status + (f": {errors[0].get('title', '')}" if errors else "")
            db.commit()
    finally:
        db.close()


@router.post("/webhook")
async def inbound(request: Request, background: BackgroundTasks):
    raw = await request.body()
    if not signature_ok(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "Invalid signature")
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Invalid JSON")
    queued = 0
    db = dbm.SessionLocal()
    try:
        for entry in data.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                A.remember_wa_number(db, (value.get("metadata") or {}).get("display_phone_number", ""))
                for msg in value.get("messages", []) or []:
                    mid, wa_from = msg.get("id"), norm_mobile(msg.get("from"))
                    if not mid or not wa_from:
                        continue
                    db.add(ProcessedEvent(event_id=mid))   # also commits a learned display number
                    try:
                        db.commit()
                    except IntegrityError:           # duplicate delivery from Meta -> ignore
                        db.rollback()
                        continue
                    background.add_task(process_inbound, wa_from, mid, extract_text(msg))
                    queued += 1
                for st in value.get("statuses", []) or []:
                    if st.get("id") and st.get("status"):
                        background.add_task(process_status, st["id"], st["status"], st.get("errors"))
        db.commit()
    finally:
        db.close()
    return {"received": True, "queued": queued}


# ------------------------------------------------------------------ test sender
class TemplateIn(BaseModel):
    to: str
    template: str = "hello_world"
    language: str = "en_US"
    params: list[str] = []


@router.post("/send-template")
def send_template_endpoint(body: TemplateIn, caller: Caller = Depends(require_api_key)):
    require_admin(caller)
    to = norm_mobile(body.to)
    if not to:
        raise HTTPException(400, detail={"error": "invalid_mobile", "message": "Give the number with country code, e.g. 919876543210"})
    status, mid = send_template(to, body.template, body.language, body.params or None)
    db = dbm.SessionLocal()
    try:
        core.log_message(db, None, "out", f"[template {body.template}] to {to[-4:]}", channel="whatsapp",
                         external_id=mid, status=status)
        db.commit()
    finally:
        db.close()
    return {"status": status, "message_id": mid, "whatsapp_configured": settings.whatsapp_configured}
