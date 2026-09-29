"""Result payloads (shared by /v1/results, /v1/referrals/{ref}, web chat) and result callbacks."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from . import db as dbm
from .conversation.core import public_answers
from .db import ChatSession, OutreachMessage, OutreachRecipient, Referral, SourceSystem, Suggestion, utcnow
from .facts import mask_mobile

log = logging.getLogger(__name__)

# Tests replace this with httpx.MockTransport so no real HTTP calls are made.
TEST_TRANSPORT = None


def http_client(timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, transport=TEST_TRANSPORT) if TEST_TRANSPORT else httpx.Client(timeout=timeout)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="microseconds") + "Z" if dt else None


def session_result(db: DB, s: ChatSession, referral: Referral | None = None) -> dict:
    if referral is None and s.referral_id:
        referral = db.get(Referral, s.referral_id)
    sugg = db.execute(select(Suggestion).where(Suggestion.session_id == s.id).order_by(Suggestion.rank)).scalars().all()
    a = s.answers or {}
    return {
        "session_id": s.public_id,
        "channel": s.channel,
        "source_system": s.source_system,
        "external_ref": referral.external_ref if referral else None,
        "referral_reason": referral.reason if referral else None,
        "status": s.status,
        "state": s.state,
        "language": s.language,
        "mobile_masked": mask_mobile(s.wa_id or (referral.mobile if referral else None)),
        "prefill_used": bool(a.get("_prefill_used")),
        "answers": public_answers(s),
        "eligible_count": s.eligible_count,
        "suggested_schemes": [{"rank": x.rank, "scheme_id": x.scheme_id, "name": x.scheme_name,
                               "benefit": x.benefit, "apply_url": x.apply_url, "shown_to_student": x.shown}
                              for x in sugg],
        "entry": entry_view(db, s, referral),
        "feedback": {"rating": s.feedback_rating, "comment": s.feedback_comment} if s.feedback_rating else None,
        "share_code": s.share_code,
        "peer_referrals_count": _peer_count(db, s) if s.share_code else 0,
        "rule_version": a.get("_rule_version"),
        "eligibility_as_of": a.get("_as_of"),
        "started_at": iso(s.started_at),
        "updated_at": iso(s.updated_at),
        "completed_at": iso(s.completed_at),
    }


def _peer_count(db: DB, s: ChatSession) -> int:
    from .attribution import peer_referral_count
    return peer_referral_count(db, s)


def entry_view(db: DB, s: ChatSession, referral: Referral | None = None) -> dict:
    o = db.get(OutreachMessage, s.outreach_id) if s.outreach_id else None
    rec = db.get(OutreachRecipient, s.outreach_recipient_id) if s.outreach_recipient_id else None
    referrer = db.get(ChatSession, s.referrer_session_id) if s.referrer_session_id else None
    same_tenant = o is not None and o.source_system == s.source_system
    return {"source": s.entry_source, "channel": s.channel,
            "outreach_message_id": o.message_id if same_tenant else None,
            "outreach_code": o.code if o else None,
            "campaign": o.campaign if same_tenant else None,
            "outreach_channel": o.channel if o else None,
            "recipient_ref": rec.recipient_ref if (rec and same_tenant) else None,
            "referrer_share_code": referrer.share_code if referrer else (s.first_touch or {}).get("share_code"),
            "first_touch": s.first_touch or {},
            "first_touch_at": (s.first_touch or {}).get("at")}


def referral_view(db: DB, r: Referral) -> dict:
    sessions = db.execute(select(ChatSession).where(ChatSession.referral_id == r.id)
                          .order_by(ChatSession.id.desc())).scalars().all()
    latest = next((x for x in sessions if x.status != "RESTARTED"), sessions[0] if sessions else None)
    return {
        "external_ref": r.external_ref, "source_system": r.source_system, "status": r.status,
        "reason": r.reason, "name": r.name, "mobile_masked": mask_mobile(r.mobile), "language": r.language,
        "known_facts": r.facts or {}, "invite_status": r.invite_status, "callback_status": r.callback_status,
        "created_at": iso(r.created_at), "updated_at": iso(r.updated_at),
        "sessions_count": len(sessions),
        "latest_result": session_result(db, latest, r) if latest else None,
    }


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def push_callback(session_pk: int) -> None:
    """Background task: POST the session result to the source system's callback URL, if one is set."""
    db = dbm.SessionLocal()
    try:
        s = db.get(ChatSession, session_pk)
        if not s or not s.source_system:
            return
        src = db.execute(select(SourceSystem).where(SourceSystem.name == s.source_system)).scalar_one_or_none()
        if not src or not src.callback_url:
            return
        payload = {"event": "discovery.result", "sent_at": iso(utcnow()), "result": session_result(db, s)}
        body = json.dumps(payload, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json", "User-Agent": "mosje-p2/1.0"}
        if src.callback_secret:
            headers["X-P2-Signature"] = sign(src.callback_secret, body)
        try:
            with http_client() as c:
                resp = c.post(src.callback_url, content=body, headers=headers)
            status = f"{resp.status_code} at {iso(utcnow())}"
        except Exception as e:  # noqa: BLE001
            status = f"error {type(e).__name__} at {iso(utcnow())}"
            log.warning("Callback to %s failed: %s", src.name, e)
        if s.referral_id:
            ref = db.get(Referral, s.referral_id)
            if ref:
                ref.callback_status = status[:200]
        db.commit()
    finally:
        db.close()
