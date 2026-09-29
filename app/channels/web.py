"""Web channel adapter: REST chat API used by the /companion widget or any Product 1 web app.

POST /v1/chat/sessions                  start a chat (X-API-Key, or public if COMPANION_PUBLIC=true)
POST /v1/chat/sessions/{id}/messages    send the user's text, get the bot reply (JSON)
GET  /v1/chat/sessions/{id}             session state, transcript and result
Auth for the last two: X-Session-Token (returned at creation) or the owning X-API-Key.
"""
from __future__ import annotations

import hmac
import secrets
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Security
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import attribution as A
from .. import results
from ..config import settings
from ..conversation import core
from ..db import ChatSession, Message, Referral, get_db
from ..security import Caller, api_key_header, require_api_key

router = APIRouter(prefix="/v1/chat", tags=["web chat"])


class StartIn(BaseModel):
    external_ref: Optional[str] = Field(None, description="Referral to pre-fill from (needs X-API-Key)")
    source_system: Optional[str] = Field(None, description="Only with the admin key")
    language: Optional[str] = Field(None, pattern="^(en|hi)$")
    entry: Optional[dict] = Field(None, description="Entry-source params from the page URL: src, om, r, ref, utm_*",
                                  examples=[{"src": "outreach", "om": "OM-7K3QPX", "r": "R8M2KD4TZ"}])


class MessageIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)


def _optional_caller(request: Request, x_api_key: Optional[str] = Security(api_key_header)) -> Optional[Caller]:
    if not x_api_key and not request.headers.get("authorization", "").lower().startswith("bearer "):
        return None
    return require_api_key(request, x_api_key)


def companion_url(public_id: str, token: str) -> str:
    base = settings.public_base_url or ""
    return f"{base}/companion?session={public_id}&token={token}"


@router.post("/sessions", status_code=201)
def create_session(body: StartIn, background: BackgroundTasks, db: DB = Depends(get_db),
                   caller: Optional[Caller] = Depends(_optional_caller)):
    referral, source = None, None
    if caller is None:
        if not settings.companion_public:
            raise HTTPException(401, detail={"error": "missing_api_key",
                                             "message": "Public companion sessions are disabled (COMPANION_PUBLIC=false)."})
        if body.external_ref or body.source_system:
            raise HTTPException(401, detail={"error": "missing_api_key",
                                             "message": "external_ref / source_system need an X-API-Key."})
    else:
        source = caller.resolve_source(body.source_system, required=True)
        if body.external_ref:
            referral = db.execute(select(Referral).where(Referral.source_system == source,
                                                         Referral.external_ref == body.external_ref)).scalar_one_or_none()
            if not referral:
                raise HTTPException(404, detail={"error": "referral_not_found",
                                                 "message": f"No referral '{body.external_ref}' for '{source}'."})
    attr = A.from_web_params(db, body.entry)
    if attr.referral is not None and referral is None and caller is None:
        referral = attr.referral            # per-recipient outreach link (opaque code) -> that referral
    token = secrets.token_urlsafe(24)
    s, reply = core.start_session(db, channel="web", referral=referral, source_system=source,
                                  language=body.language, token_hash=core.hash_token(token), attribution=attr)
    core.log_message(db, s, "out", core.render_text(reply), channel="web")
    s.last_reply = reply.to_dict()
    db.commit()
    return {"session_id": s.public_id, "session_token": token, "channel": "web",
            "source_system": s.source_system, "external_ref": referral.external_ref if referral else None,
            "entry_source": s.entry_source,
            "companion_url": companion_url(s.public_id, token), "reply": reply.to_dict()}


def _load(db: DB, public_id: str, token: Optional[str], caller: Optional[Caller]) -> ChatSession:
    s = db.execute(select(ChatSession).where(ChatSession.public_id == public_id,
                                             ChatSession.channel == "web")).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail={"error": "session_not_found", "message": "Unknown session id."})
    if token and s.token_hash and hmac.compare_digest(core.hash_token(token), s.token_hash):
        return s
    if caller and (caller.is_admin or caller.source_system == s.source_system):
        return s
    raise HTTPException(401, detail={"error": "invalid_session_token",
                                     "message": "Send X-Session-Token (from session creation) or the owning X-API-Key."})


@router.post("/sessions/{session_id}/messages")
def post_message(session_id: str, body: MessageIn, background: BackgroundTasks, db: DB = Depends(get_db),
                 x_session_token: Optional[str] = Header(default=None),
                 caller: Optional[Caller] = Depends(_optional_caller)):
    s = _load(db, session_id, x_session_token, caller)
    core.log_message(db, s, "in", body.text, channel="web")
    s2, reply = core.handle_message(db, s, body.text)
    if not reply.silent:
        core.log_message(db, s2, "out", core.render_text(reply), channel="web")
        s2.last_reply = reply.to_dict()
    db.commit()
    if "completed" in reply.events or "opted_out" in reply.events:
        background.add_task(results.push_callback, s2.id)
    return {"session_id": s2.public_id, "new_session": s2.id != s.id, "status": s2.status,
            "entry_source": s2.entry_source, "reply": reply.to_dict()}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(default=None),
                caller: Optional[Caller] = Depends(_optional_caller)):
    s = _load(db, session_id, x_session_token, caller)
    msgs = db.execute(select(Message).where(Message.session_id == s.id).order_by(Message.id)).scalars().all()
    return {"result": results.session_result(db, s), "last_reply": s.last_reply,
            "transcript": [{"direction": m.direction, "text": m.body, "at": results.iso(m.created_at)} for m in msgs]}
