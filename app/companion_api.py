"""Web companion API (Update 3) - used by the mobile-first /companion page and open to other teams.

The chat itself still runs on /v1/chat/sessions (channel-agnostic engine). These endpoints add what the new
WhatsApp-native companion needs (Product Vision V1.0):

  GET    /v1/companion/config                              languages, States (+ likely), speech status, WA number
  POST   /v1/companion/open                                exchange a one-time WhatsApp link code (WL-...) for a web session
  POST   /v1/companion/sessions/{id}/interpret             "You mean X, right?" - understand a typed answer (no state change)
  GET    /v1/companion/sessions/{id}/results               rich scheme cards + summary (count, ₹/year, closest last date)
  GET    /v1/companion/sessions/{id}/schemes/{scheme_id}   scheme details (why you match, documents, steps)
  POST   /v1/companion/sessions/{id}/events                funnel events (web_opened, scheme_viewed, apply_clicked ...)
  POST   /v1/companion/sessions/{id}/feedback              rating 1-5 + comment + context -> also returns refer links
  POST   /v1/companion/sessions/{id}/referral              refer-a-friend links (REF code -> src=referral&ref=REF-...)
  POST   /v1/companion/sessions/{id}/save                  Save on WhatsApp (one tap / SAVE code / parent OK code)
  GET    /v1/companion/sessions/{id}/save-status/{code}    poll until the student (or parent) sent the code on WhatsApp
  GET    /v1/companion/me                                  My schemes (header X-Student-Token)
  PUT    /v1/companion/me/preferences                      last-date / new-scheme / renewal reminders on/off
  POST   /v1/companion/me/schemes                          save more schemes
  PATCH  /v1/companion/me/schemes/{scheme_id}              tracker status, documents I have, last date, renewal
  DELETE /v1/companion/me/schemes/{scheme_id}              remove a saved scheme
  DELETE /v1/companion/me                                  delete my data (number, answers, saved schemes, reminders)
  POST   /v1/companion/me/referral                         refer-a-friend links for a saved student
  GET    /v1/companion/feedback          (X-API-Key)       feedback list, tenant-scoped
  GET    /v1/companion/funnel            (X-API-Key)       funnel counts: opened -> answered -> saved -> applied
  POST   /v1/jobs/run-reminders          (admin key)       send due reminders + new-scheme alerts (run daily)
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from . import attribution as A
from . import scheme_view as V
from . import students as ST
from .channels.web import _load, _optional_caller, companion_url
from .config import settings
from .conversation import core
from .conversation.texts import LANG_ORDER, LANGS, lang_label, t
from .conversation.understand import extract_all, understand
from .db import (ChatSession, Event, Feedback, LinkCode, Reminder, SavedScheme, ShareEvent, Student, Suggestion,
                 get_db, utcnow)
from .eligibility import get_engine
from .facts import norm_mobile, states
from .security import Caller, require_admin, require_api_key
from .speech import speech_status

router = APIRouter(prefix="/v1/companion", tags=["web companion"])
jobs = APIRouter(prefix="/v1/jobs", tags=["jobs"])
LIKELY_DEFAULT = ["Uttar Pradesh", "Bihar", "Maharashtra", "West Bengal", "Rajasthan", "Madhya Pradesh"]
EVENT_RX = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


def _session(db: DB, sid: str, token: Optional[str], caller: Optional[Caller]) -> ChatSession:
    return _load(db, sid, token, caller)


def _student(db: DB, token: Optional[str]) -> Student:
    st = ST.student_by_token(db, token)
    if st is None:
        raise HTTPException(401, detail={"error": "invalid_student_token",
                                         "message": "Send X-Student-Token (returned when the schemes were saved)."})
    return st


# ------------------------------------------------------------------ config / open
@router.get("/config")
def config(db: DB = Depends(get_db)):
    rows = db.execute(select(ChatSession.answers).where(ChatSession.completed_at.is_not(None))
                      .order_by(ChatSession.id.desc()).limit(500)).scalars().all()
    top = [s for s, _ in Counter((a or {}).get("state") for a in rows if (a or {}).get("state")).most_common(6)]
    likely = list(dict.fromkeys(top + LIKELY_DEFAULT))[:6]
    num = A.wa_number(db)
    return {"languages": [{"code": c, "label": lang_label(c), "en": LANGS[c]["en"], "native": LANGS[c]["native"]}
                          for c in LANG_ORDER],
            "states": states(), "likely_states": [s for s in likely if s in states()],
            "speech": speech_status(), "wa_number": num, "wa_hi_link": A.wa_link(db, "Hi") if num else None,
            "link_ttl_hours": settings.link_ttl_hours, "save_consent_text": ST.CONSENT_TEXT,
            "never_pay": "Applying is free. Never pay anyone.", "data_note": "Synthetic / test scheme data."}


class OpenIn(BaseModel):
    code: str = Field(..., min_length=4, max_length=60)
    entry: Optional[dict] = None


@router.post("/open", status_code=201)
def open_link(body: OpenIn, db: DB = Depends(get_db)):
    """One-time WhatsApp link -> web session for the same number (journeys 1 and 2).
    A used / expired / forwarded code gives an anonymous session instead (never someone else's data)."""
    import secrets
    lc = ST.find_code(db, body.code, "WEB_LINK")
    usable = ST.code_usable(lc)
    wa_s = db.get(ChatSession, lc.session_id) if usable and lc.session_id else None
    token = secrets.token_urlsafe(24)
    if usable:
        lc.used_at = utcnow()
        lang = (wa_s.language if wa_s else None) or (lc.payload or {}).get("language")
        s, reply = core.start_session(db, channel="web", wa_id=lc.wa_id, token_hash=core.hash_token(token),
                                      inherit_from=wa_s, language=lang, source_system=wa_s.source_system if wa_s else None,
                                      attribution=None if wa_s else A.from_web_params(db, body.entry))
        s.opened_via = "wa_link"
        answers = core.public_answers(wa_s) if wa_s else {}
        if answers and s.consent_status == "AGREED":
            core._set_answers(s, **answers)
            reply = core._advance(db, s)
    else:
        s, reply = core.start_session(db, channel="web", token_hash=core.hash_token(token),
                                      attribution=A.from_web_params(db, body.entry))
        s.opened_via = "wa_link_expired" if lc else "wa_link_invalid"
    st = ST.student_for_wa(db, s.wa_id) if s.wa_id else None
    student_token = ST.issue_token(st) if st is not None and st.status != "DELETED" else None
    if st is not None:
        s.student_id = st.id
    core.log_message(db, s, "out", core.render_text(reply), channel="web")
    s.last_reply = reply.to_dict()
    db.add(Event(session_id=s.id, name="web_opened", data={"via": s.opened_via}))
    db.commit()
    return {"session_id": s.public_id, "session_token": token, "linked": usable, "status": s.status,
            "reason": None if usable else ("link_used_or_expired" if lc else "link_invalid"),
            "screen": (lc.payload or {}).get("screen", "chat") if usable else "chat",
            "phone_masked": ST.mask_mobile(s.wa_id) if s.wa_id else None, "student_token": student_token,
            "entry_source": s.entry_source, "companion_url": companion_url(s.public_id, token), "reply": reply.to_dict()}


# ------------------------------------------------------------------ chat helpers
class InterpretIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    key: Optional[str] = Field(None, pattern="^(state|class_passed|gender|annual_family_income|category)$")


@router.post("/sessions/{sid}/interpret")
def interpret(sid: str, body: InterpretIn, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
              caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    view = core._cur_view(s)
    key = body.key or (view[4:] if view.startswith("ASK_") else None)
    if not key:
        return {"key": None, "understood": False}
    v = core.parse_answer(key, body.text, s.language)
    exact = v is not core.MISSING
    if not exact:
        v = understand(key, body.text)
    if v is None or v is core.MISSING:
        return {"key": key, "understood": False}
    facts = core.income_facts(v) if key == "annual_family_income" else {key: v}
    send = (f"{v} per year" if isinstance(v, int) else str(v)) if key == "annual_family_income" else str(v)
    also = {k: core.fmt_fact(k, x, s.language, {k: x}) for k, x in extract_all(body.text).items()
            if k != key and k not in (s.answers or {})}
    return {"key": key, "understood": True, "exact": exact, "value": v, "send": send,
            "label": core.fmt_fact(key, facts.get(key, v), s.language, facts), "also": also}


def _profile(s: ChatSession) -> list[dict]:
    a = core.public_answers(s)
    return [{"key": k, "field": t(s.language, f"f_{k}"),
             "value": core.fmt_fact(k, a[k], s.language, a) if k in a else None} for k in core.QUESTION_KEYS]


@router.get("/sessions/{sid}/results")
def results_view(sid: str, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
                 caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    facts = core.public_answers(s)
    eng = get_engine()
    sugg = db.execute(select(Suggestion).where(Suggestion.session_id == s.id).order_by(Suggestion.rank)).scalars().all()
    cards = [V.card(eng.by_id[x.scheme_id], facts, x.rank) for x in sugg if x.scheme_id in eng.by_id]
    saved = set()
    if s.student_id:
        saved = set(db.execute(select(SavedScheme.scheme_id).where(SavedScheme.student_id == s.student_id)).scalars())
    for c in cards:
        c["saved"] = c["scheme_id"] in saved
    return {"session_id": s.public_id, "completed": s.completed_at is not None, "language": s.language,
            "profile": _profile(s), "summary": V.summary(cards), "cards": cards,
            "linked_phone": ST.mask_mobile(s.wa_id) if s.wa_id else None,
            "rule_version": (s.answers or {}).get("_rule_version"), "data_note": "Synthetic / test scheme data."}


@router.get("/sessions/{sid}/schemes/{scheme_id}")
def scheme_detail(sid: str, scheme_id: str, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
                  caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    rule = get_engine().by_id.get(scheme_id)
    if rule is None:
        raise HTTPException(404, detail={"error": "scheme_not_found", "message": "Unknown scheme id."})
    d = V.detail(rule, core.public_answers(s))
    db.add(Event(session_id=s.id, name="scheme_viewed", scheme_id=scheme_id))
    db.commit()
    return d


class EventIn(BaseModel):
    name: str = Field(..., max_length=40)
    scheme_id: Optional[str] = Field(None, max_length=20)
    data: dict = Field(default_factory=dict)


@router.post("/sessions/{sid}/events", status_code=202)
def event(sid: str, body: EventIn, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
          caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    if not EVENT_RX.match(body.name):
        raise HTTPException(400, detail={"error": "invalid_event", "message": "name: lowercase letters, digits, _"})
    data = {str(k)[:30]: (v if isinstance(v, (int, float, bool)) else str(v)[:100]) for k, v in list(body.data.items())[:10]}
    db.add(Event(session_id=s.id, student_id=s.student_id, name=body.name, scheme_id=body.scheme_id, data=data))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ feedback + refer a friend
def _refer_links(db: DB, s: Optional[ChatSession], st: Optional[Student]) -> dict:
    code = st.share_code if st is not None and st.share_code else None
    lang = (s.language if s is not None else None) or (st.language if st is not None else None)
    links = A.share_links(db, s, code=code, lang=lang)
    if st is not None and not st.share_code:
        st.share_code = links["share_code"]
    return links


class FeedbackIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)
    context: dict = Field(default_factory=dict, description='e.g. {"screen": "summary", "scheme_id": "SCH_0012"}')


@router.post("/sessions/{sid}/feedback", status_code=201)
def feedback(sid: str, body: FeedbackIn, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
             caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    ctx = {str(k)[:30]: str(v)[:100] for k, v in list(body.context.items())[:10]}
    fb = core.record_feedback(db, s, body.rating, body.comment, channel="web", context=ctx)
    st = db.get(Student, s.student_id) if s.student_id else None
    links = _refer_links(db, s, st)
    db.commit()
    return {"feedback_id": fb.id, "thanks": True, "refer": links}


class ReferIn(BaseModel):
    via: Optional[str] = Field(None, pattern="^(whatsapp|copy|native|email|sms|other)$")
    kind: str = Field("refer", pattern="^(refer|scheme|parent)$")
    scheme_id: Optional[str] = Field(None, max_length=20)


@router.post("/sessions/{sid}/referral")
def referral(sid: str, body: ReferIn, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
             caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    st = db.get(Student, s.student_id) if s.student_id else None
    links = _refer_links(db, s, st)
    db.add(ShareEvent(share_code=links["share_code"], session_id=s.id, student_id=st.id if st else None,
                      kind=body.kind, via=body.via, scheme_id=body.scheme_id))
    db.commit()
    return dict(links, referrals_started=A.peer_referral_count(db, s))


# ------------------------------------------------------------------ Save on WhatsApp
class SaveIn(BaseModel):
    scheme_ids: list[str] = Field(default_factory=list, max_length=100)
    scope: str = Field("selected", pattern="^(selected|all)$")
    consent: bool = Field(..., description="The student agreed to: " + ST.CONSENT_TEXT)
    age_band: str = Field("18plus", pattern="^(18plus|u18)$")
    phone: Optional[str] = Field(None, max_length=20, description="Journey 3 only (number not known yet)")
    remind: dict = Field(default_factory=lambda: {"deadline": True, "new": True, "renew": True})


@router.post("/sessions/{sid}/save")
def save(sid: str, body: SaveIn, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
         x_student_token: Optional[str] = Header(None), caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    if not body.consent:
        raise HTTPException(400, detail={"error": "consent_required", "message": ST.CONSENT_TEXT})
    ids = body.scheme_ids
    if body.scope == "all" or not ids:
        ids = [x.scheme_id for x in db.execute(select(Suggestion).where(Suggestion.session_id == s.id)
                                               .order_by(Suggestion.rank)).scalars()]
    if not ids:
        raise HTTPException(400, detail={"error": "nothing_to_save", "message": "Find scholarships first."})
    remind = {k: bool(body.remind.get(k, True)) for k in ("deadline", "new", "renew")}
    known = ST.student_by_token(db, x_student_token)
    if body.age_band == "u18":
        child = norm_mobile(body.phone) if body.phone else s.wa_id or (known.wa_id if known else None)
        if not child:
            raise HTTPException(400, detail={"error": "phone_required", "message": "Enter your WhatsApp number."})
        lc = ST.new_code(db, "PARENT_OK", wa_id=child, session_id=s.id,
                         payload={"child_wa_id": child, "scheme_ids": ids, "remind": remind})
        share = ST.parent_share_message(db, lc.code)
        db.commit()
        return {"status": "parent_pending", "code": lc.code, "expires_at": lc.expires_at.isoformat() + "Z",
                "parent": share, "wa_number": A.wa_number(db), "phone_masked": ST.mask_mobile(child)}
    wa_id = s.wa_id or (known.wa_id if known else None)
    if wa_id:                                        # journeys 1-2 (opened from WhatsApp) or a returning browser
        st = ST.upsert_student(db, wa_id, s, age_band="18plus", remind=remind)
        rows = ST.save_schemes(db, st, ids)
        token = ST.issue_token(st)
        db.add(Event(session_id=s.id, student_id=st.id, name="saved", data={"n": len(rows), "how": "one_tap"}))
        db.commit()
        return {"status": "saved", "saved": len(rows), "student_token": token, "phone_masked": ST.mask_mobile(wa_id),
                "me": ST.me_view(db, st)}
    phone = norm_mobile(body.phone) if body.phone else None
    if body.phone and not phone:
        raise HTTPException(400, detail={"error": "invalid_mobile", "message": "Enter a 10-digit mobile number."})
    lc = ST.new_code(db, "SAVE_CONFIRM", wa_id=phone, session_id=s.id,
                     payload={"scheme_ids": ids, "remind": remind, "age_band": "18plus", "phone_entered": phone})
    text = ST.save_wa_text(lc.code)
    db.commit()
    return {"status": "confirm_pending", "code": lc.code, "expires_at": lc.expires_at.isoformat() + "Z",
            "wa_text": text, "wa_link": A.wa_link(db, text), "wa_number": A.wa_number(db),
            "phone_masked": ST.mask_mobile(phone) if phone else None}


@router.get("/sessions/{sid}/save-status/{code}")
def save_status(sid: str, code: str, db: DB = Depends(get_db), x_session_token: Optional[str] = Header(None),
                caller: Optional[Caller] = Depends(_optional_caller)):
    s = _session(db, sid, x_session_token, caller)
    lc = ST.find_code(db, code, "PARENT_OK" if code.upper().startswith("OK-") else "SAVE_CONFIRM")
    if lc is None or lc.session_id != s.id:
        raise HTTPException(404, detail={"error": "code_not_found", "message": "Unknown code for this session."})
    if lc.used_at is None:
        return {"status": "expired" if lc.expires_at <= utcnow() else "pending"}
    st = db.get(Student, lc.student_id) if lc.student_id else None
    out = {"status": "confirmed", "phone_masked": ST.mask_mobile(st.wa_id) if st else None}
    p = dict(lc.payload or {})
    if st is not None and not p.get("token_issued"):    # the token is handed to this browser once
        out["student_token"] = ST.issue_token(st)
        p["token_issued"] = True
        lc.payload = p
        s.student_id = st.id
        out["me"] = ST.me_view(db, st)
    db.commit()
    return out


# ------------------------------------------------------------------ My schemes
@router.get("/me")
def me(db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    return ST.me_view(db, _student(db, x_student_token))


class PrefsIn(BaseModel):
    deadline: Optional[bool] = None
    new: Optional[bool] = None
    renew: Optional[bool] = None
    language: Optional[str] = Field(None, pattern="^(en|hi|bn|as|kn|ta|te|ml|or|bho|mai|gu|mr|pa)$")


@router.put("/me/preferences")
def prefs(body: PrefsIn, db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    st = _student(db, x_student_token)
    for k in ("deadline", "new", "renew"):
        v = getattr(body, k)
        if v is not None:
            setattr(st, f"remind_{k}", v)
    if body.language:
        st.language = body.language
    ST.plan_reminders(db, st)
    db.commit()
    return ST.me_view(db, st)


class SchemesIn(BaseModel):
    scheme_ids: list[str] = Field(..., min_length=1, max_length=100)


@router.post("/me/schemes")
def add_schemes(body: SchemesIn, db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    st = _student(db, x_student_token)
    ST.save_schemes(db, st, body.scheme_ids)
    db.commit()
    return ST.me_view(db, st)


class TrackIn(BaseModel):
    status: Optional[str] = Field(None, pattern="^(saved|docs|applied|result|approved|rejected)$")
    docs_have: Optional[dict] = None
    last_date: Optional[date] = None
    renewal_needed: Optional[bool] = None
    renewal_date: Optional[date] = None


@router.patch("/me/schemes/{scheme_id}")
def track(scheme_id: str, body: TrackIn, db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    st = _student(db, x_student_token)
    data = body.model_dump(exclude_unset=True)
    for k in ("last_date", "renewal_date"):
        if k in data and data[k] is not None:
            data[k] = data[k].isoformat()
    try:
        row = ST.update_saved(db, st, scheme_id, data)
    except KeyError:
        raise HTTPException(404, detail={"error": "not_saved", "message": "This scheme is not in My schemes."})
    db.commit()
    return {"scheme": ST.saved_view(row), "me": ST.me_view(db, st)}


@router.delete("/me/schemes/{scheme_id}")
def unsave(scheme_id: str, db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    st = _student(db, x_student_token)
    row = db.execute(select(SavedScheme).where(SavedScheme.student_id == st.id,
                                               SavedScheme.scheme_id == scheme_id)).scalar_one_or_none()
    if row is not None:
        db.query(Reminder).filter(Reminder.saved_id == row.id).delete()
        db.delete(row)
        db.flush()
    db.commit()
    return ST.me_view(db, st)


@router.delete("/me")
def delete_me(db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    st = _student(db, x_student_token)
    ST.delete_student(db, st)
    db.commit()
    return {"deleted": True}


@router.post("/me/referral")
def me_referral(body: ReferIn, db: DB = Depends(get_db), x_student_token: Optional[str] = Header(None)):
    st = _student(db, x_student_token)
    s = db.get(ChatSession, st.first_session_id) if st.first_session_id else None
    if s is None and not st.share_code:
        raise HTTPException(409, detail={"error": "no_session", "message": "Start a chat first."})
    links = _refer_links(db, s, st)
    db.add(ShareEvent(share_code=links["share_code"], student_id=st.id, kind=body.kind, via=body.via,
                      scheme_id=body.scheme_id))
    db.commit()
    return links


# ------------------------------------------------------------------ partner / admin views
@router.get("/feedback")
def feedback_list(source_system: Optional[str] = None, limit: int = Query(100, ge=1, le=1000),
                  db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    src = caller.resolve_source(source_system)
    q = select(Feedback).order_by(Feedback.id.desc()).limit(limit)
    if src:
        q = q.where(Feedback.source_system == src)
    rows = db.execute(q).scalars().all()
    avg = (sum(r.rating for r in rows) / len(rows)) if rows else None
    return {"count": len(rows), "average_rating": round(avg, 2) if avg else None,
            "feedback": [{"id": r.id, "rating": r.rating, "comment": r.comment, "channel": r.channel,
                          "context": r.context, "language": r.language, "source_system": r.source_system,
                          "created_at": r.created_at.isoformat() + "Z"} for r in rows]}


@router.get("/funnel")
def funnel(source_system: Optional[str] = None, db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    src = caller.resolve_source(source_system)
    sq = select(ChatSession.id)
    if src:
        sq = sq.where(ChatSession.source_system == src)
    ids = set(db.execute(sq).scalars())
    sessions = db.execute(select(ChatSession).where(ChatSession.id.in_(ids))).scalars().all() if ids else []
    ev = Counter(n for n, sid in db.execute(select(Event.name, Event.session_id)) if sid in ids)
    stq = select(Student)
    if src:
        stq = stq.where(Student.source_system == src)
    sts = db.execute(stq).scalars().all()
    st_ids = {x.id for x in sts}
    saved = db.execute(select(SavedScheme.status, SavedScheme.student_id)).all()
    track = Counter(stt for stt, sid in saved if sid in st_ids)
    rem = Counter(stt for stt, sid in db.execute(select(Reminder.status, Reminder.student_id)) if sid in st_ids)
    fb = [r for r, sid in db.execute(select(Feedback.rating, Feedback.session_id)) if sid in ids]
    return {"source_system": src or "all",
            "sessions": len(sessions), "by_entry_source": dict(Counter(s.entry_source or "UNKNOWN" for s in sessions)),
            "by_channel": dict(Counter(s.channel for s in sessions)),
            "completed": sum(1 for s in sessions if s.completed_at), "events": dict(ev),
            "students_saved": len(sts), "students_stopped": sum(1 for x in sts if x.status == "STOPPED"),
            "tracker": dict(track), "reminders": dict(rem),
            "feedback": {"count": len(fb), "average": round(sum(fb) / len(fb), 2) if fb else None},
            "peer_referral_sessions": sum(1 for s in sessions if s.entry_source == A.PEER)}


class JobIn(BaseModel):
    dry_run: bool = False
    date: Optional[date] = None


@jobs.post("/run-reminders")
def run_reminders(body: JobIn = JobIn(), db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    require_admin(caller)
    out = ST.run_reminders(db, body.date, body.dry_run)
    db.commit()
    return out
