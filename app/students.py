"""Save on WhatsApp, My schemes, application tracker and reminders (Update 3, Product Vision V1.0 sections 4-6).

Data kept for a saved student (and nothing else): WhatsApp number, language, the 5 answers, saved schemes with
tracker status / dates, and alert settings. Never name, Aadhaar, bank details or documents.

One-time codes (p2_link_codes):
  WL-...      WhatsApp -> web. The bot sends /companion?c=WL-...; the code is tied to the sender's number, works
              once and expires (ONE_TIME_LINK_TTL_HOURS). A forwarded/used link opens an anonymous page only.
  SAVE-XXXXX  web -> WhatsApp (journey 3, no OTP). The student sends "Hi ... Code SAVE-XXXXX" from WhatsApp; the
              number that sends it is the number we save (this proves the number).
  OK-XXXXX    under 18: a parent sends "YES Code OK-XXXXX" from their WhatsApp before anything is stored.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from . import attribution as A
from . import scheme_view as V
from .config import settings
from .db import ChatSession, LinkCode, Reminder, SavedScheme, Student, utcnow
from .eligibility import get_engine
from .facts import mask_mobile

CONSENT_TEXT = "We'll keep your number, your answers and saved schemes to send reminders. Reply STOP anytime."
CONSENT_TEXT_VERSION = "p2-save-2026-10-02"
TRACK_STATES = ["saved", "docs", "applied", "result", "approved", "rejected"]
DONE_STATES = {"applied", "result", "approved", "rejected"}       # no more last-date reminders
CODE_RE = re.compile(r"\b(SAVE|OK)-([A-Z0-9]{5})\b", re.I)
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"                      # no 0/O/1/I


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _short(n: int = 5) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


# ------------------------------------------------------------------ one-time codes
def new_code(db: DB, kind: str, *, wa_id: str | None = None, session_id: int | None = None,
             student_id: int | None = None, payload: dict | None = None, ttl_hours: int | None = None) -> LinkCode:
    prefix = {"WEB_LINK": "WL-", "SAVE_CONFIRM": "SAVE-", "PARENT_OK": "OK-"}[kind]
    for _ in range(20):
        code = prefix + (secrets.token_urlsafe(12) if kind == "WEB_LINK" else _short())
        if not db.execute(select(LinkCode.id).where(LinkCode.code == code)).first():
            break
    lc = LinkCode(code=code, kind=kind, wa_id=wa_id, session_id=session_id, student_id=student_id,
                  payload=payload or {},
                  expires_at=utcnow() + timedelta(hours=ttl_hours or settings.link_ttl_hours))
    db.add(lc)
    db.flush()
    return lc


def find_code(db: DB, code: str, kind: str) -> Optional[LinkCode]:
    code = (code or "").strip()
    if kind != "WEB_LINK":
        code = code.upper()
    return db.execute(select(LinkCode).where(LinkCode.code == code, LinkCode.kind == kind)).scalar_one_or_none()


def code_usable(lc: Optional[LinkCode]) -> bool:
    return lc is not None and lc.used_at is None and lc.expires_at > utcnow()


def web_link_url(db: DB, s: ChatSession, screen: str = "chat") -> str:
    """One-time web link for a WhatsApp user (journeys 1 and 2)."""
    st = student_for_wa(db, s.wa_id) if s.wa_id else None
    lc = new_code(db, "WEB_LINK", wa_id=s.wa_id, session_id=s.id, student_id=st.id if st else None,
                  payload={"screen": screen, "language": s.language})
    return f"{settings.public_base_url}/companion?c={lc.code}"


# ------------------------------------------------------------------ students
def student_for_wa(db: DB, wa_id: str | None) -> Optional[Student]:
    if not wa_id:
        return None
    return db.execute(select(Student).where(Student.wa_id == wa_id)).scalar_one_or_none()


def student_by_token(db: DB, token: str | None) -> Optional[Student]:
    if not token:
        return None
    st = db.execute(select(Student).where(Student.token_hash == _hash(token))).scalar_one_or_none()
    return st if st is not None and st.status != "DELETED" else None


def issue_token(st: Student) -> str:
    """A new My-schemes token for this browser (older browsers keep working only until the next issue)."""
    token = secrets.token_urlsafe(24)
    st.token_hash = _hash(token)
    return token


def upsert_student(db: DB, wa_id: str, s: Optional[ChatSession], *, age_band: str | None = None,
                   parent_wa_id: str | None = None, remind: dict | None = None) -> Student:
    st = student_for_wa(db, wa_id)
    if st is None:
        from .conversation.core import new_public_id
        st = Student(public_id="ST-" + new_public_id()[:16], wa_id=wa_id, answers={}, seen_scheme_ids=[])
        db.add(st)
    if s is not None:
        st.language = s.language or st.language or "en"
        answers = {k: v for k, v in (s.answers or {}).items() if not k.startswith("_")}
        if answers:
            st.answers = answers
        st.entry_source = st.entry_source or s.entry_source
        st.source_system = st.source_system or s.source_system
        st.first_session_id = st.first_session_id or s.id
        st.share_code = st.share_code or A.ensure_share_code(db, s)
    st.status = "ACTIVE"
    st.age_band = age_band or st.age_band
    st.parent_wa_id = parent_wa_id or st.parent_wa_id
    st.consent_text_version, st.consent_at = CONSENT_TEXT_VERSION, utcnow()
    for k in ("deadline", "new", "renew"):
        if remind and k in remind:
            setattr(st, f"remind_{k}", bool(remind[k]))
    if not st.seen_scheme_ids and st.answers:
        st.seen_scheme_ids = [c["scheme_id"] for c in get_engine().evaluate(st.answers)["schemes"]]
    db.flush()
    if s is not None:
        s.student_id = st.id
    return st


def save_schemes(db: DB, st: Student, scheme_ids: list[str]) -> list[SavedScheme]:
    eng = get_engine()
    out = []
    for sid in dict.fromkeys(scheme_ids or []):
        rule = eng.by_id.get(sid)
        if rule is None:
            continue
        row = db.execute(select(SavedScheme).where(SavedScheme.student_id == st.id,
                                                   SavedScheme.scheme_id == sid)).scalar_one_or_none()
        if row is None:
            d = V.scheme_dates().get(sid, {})
            row = SavedScheme(student_id=st.id, scheme_id=sid, scheme_name=rule.Scheme_Name[:300], status="saved",
                              docs_have={}, last_date=d.get("last_date"),
                              renewal_needed=True if (d.get("renewal") or "") in ("yes", "y", "true", "1", "annual")
                              or d.get("renewal_date") else None, renewal_date=d.get("renewal_date"))
            db.add(row)
        out.append(row)
    db.flush()
    plan_reminders(db, st)
    return out


def delete_student(db: DB, st: Student) -> None:
    """'Delete my data': removes the saved schemes, reminders and the number itself."""
    for model in (SavedScheme, Reminder):
        db.query(model).filter(model.student_id == st.id).delete()
    db.query(LinkCode).filter(LinkCode.student_id == st.id).delete()
    for s in db.execute(select(ChatSession).where(ChatSession.student_id == st.id)).scalars():
        s.student_id = None
    db.delete(st)
    db.flush()


def stop_student(db: DB, wa_id: str) -> None:
    st = student_for_wa(db, wa_id)
    if st is not None:
        st.status = "STOPPED"
        db.query(Reminder).filter(Reminder.student_id == st.id, Reminder.status == "PENDING").update(
            {"status": "SKIPPED", "channel_status": "student replied STOP"})


def touch_inbound(db: DB, wa_id: str) -> None:
    st = student_for_wa(db, wa_id)
    if st is not None:
        st.last_inbound_at = utcnow()


# ------------------------------------------------------------------ tracker / My schemes view
def saved_view(row: SavedScheme, lang: str = "en") -> dict:
    rule = get_engine().by_id.get(row.scheme_id)
    card = V.card(rule, {}) if rule is not None else {}
    last = row.last_date or (card.get("last_date") and date.fromisoformat(card["last_date"]))
    return {"scheme_id": row.scheme_id, "name": row.scheme_name, "status": row.status,
            "docs_have": row.docs_have or {}, "documents": card.get("documents", []),
            "amount_per_year": card.get("amount_per_year"), "amount_kind": card.get("amount_kind"),
            "apply_url": card.get("apply_url"),
            "last_date": last.isoformat() if last else None, "days_left": V.days_left(last) if last else None,
            "renewal_needed": row.renewal_needed, "renewal_date": row.renewal_date.isoformat() if row.renewal_date else None,
            "status_changed_at": row.status_changed_at.isoformat() + "Z" if row.status_changed_at else None,
            "level": rule.Scheme_Level if rule else None, "state_ut": rule.Scheme_State_UT if rule else None}


def me_view(db: DB, st: Student) -> dict:
    rows = db.execute(select(SavedScheme).where(SavedScheme.student_id == st.id)
                      .order_by(SavedScheme.created_at)).scalars().all()
    saved = [saved_view(r, st.language) for r in rows]
    rem = db.execute(select(Reminder).where(Reminder.student_id == st.id, Reminder.status == "PENDING")
                     .order_by(Reminder.due_on).limit(10)).scalars().all()
    counts = {k: sum(1 for r in rows if r.status == k) for k in TRACK_STATES}
    return {"student_id": st.public_id, "phone_masked": mask_mobile(st.wa_id), "language": st.language,
            "answers": st.answers or {}, "age_band": st.age_band, "status": st.status,
            "preferences": {"deadline": st.remind_deadline, "new": st.remind_new, "renew": st.remind_renew},
            "saved": saved,
            "stats": {**{f"status_{k}": v for k, v in counts.items()}, "saved": len(rows),
                      "docs": counts["docs"], "applied": sum(1 for r in rows if r.status in DONE_STATES),
                      "approved": counts["approved"], "rejected": counts["rejected"]},
            "upcoming": [{"kind": r.kind, "due_on": r.due_on.isoformat(), "scheme_id": _rem_scheme(db, r),
                          "message": r.message} for r in rem],
            "share_code": st.share_code, "consent_text": CONSENT_TEXT}


def _rem_scheme(db: DB, r: Reminder) -> Optional[str]:
    if not r.saved_id:
        return None
    row = db.get(SavedScheme, r.saved_id)
    return row.scheme_id if row else None


def update_saved(db: DB, st: Student, scheme_id: str, data: dict) -> SavedScheme:
    row = db.execute(select(SavedScheme).where(SavedScheme.student_id == st.id,
                                               SavedScheme.scheme_id == scheme_id)).scalar_one_or_none()
    if row is None:
        raise KeyError(scheme_id)
    if data.get("status") and data["status"] in TRACK_STATES and data["status"] != row.status:
        row.status = data["status"]
        row.status_changed_at = utcnow()
    if isinstance(data.get("docs_have"), dict):
        row.docs_have = {str(k)[:20]: bool(v) for k, v in data["docs_have"].items()}
    for k in ("last_date", "renewal_date"):
        if k in data:
            v = data[k]
            setattr(row, k, date.fromisoformat(v) if v else None)
    if "renewal_needed" in data:
        row.renewal_needed = None if data["renewal_needed"] is None else bool(data["renewal_needed"])
    db.flush()
    plan_reminders(db, st)
    return row


# ------------------------------------------------------------------ reminders
def _today() -> date:
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).date()     # IST


def _want(db: DB, st: Student, row: SavedScheme | None, kind: str, due: date, msg: str, key: str, out: set):
    out.add(key)
    r = db.execute(select(Reminder).where(Reminder.student_id == st.id, Reminder.dedupe_key == key)).scalar_one_or_none()
    if r is None:
        db.add(Reminder(student_id=st.id, saved_id=row.id if row else None, kind=kind, dedupe_key=key, due_on=due,
                        status="PENDING", message=msg))
    elif r.status == "PENDING":
        r.due_on, r.message = due, msg


def plan_reminders(db: DB, st: Student, today: date | None = None) -> None:
    """(Re)compute PENDING reminders: last date -7 / -2 days (stop once Applied), documents nudge 7 days after
    "Documents pending", result check 30 days after Applied, renewal 30 days before the renewal date (+ profile refresh). Old pending ones that no longer apply are SKIPPED."""
    today = today or _today()
    wanted: set = set()
    rows = db.execute(select(SavedScheme).where(SavedScheme.student_id == st.id)).scalars().all()
    for row in rows:
        name = row.scheme_name
        if st.remind_deadline and row.last_date and row.status not in DONE_STATES:
            for n in (7, 2):
                due = row.last_date - timedelta(days=n)
                if due >= today:
                    _want(db, st, row, f"deadline_{n}", due,
                          f"⏰ {n} days left to apply for {name} (last date {row.last_date:%d %b %Y}). "
                          "Applying is free – never pay anyone.", f"deadline_{n}:{row.scheme_id}:{row.last_date}", wanted)
        if row.status == "docs" and st.remind_deadline:     # nudge if stuck at "Documents pending" (Vision 6)
            due = (row.status_changed_at or utcnow()).date() + timedelta(days=7)
            _want(db, st, row, "docs_nudge", max(due, today),
                  f"📄 Still collecting documents for {name}? Open My schemes to see how to get each one. "
                  "Applying is free – never pay anyone.", f"docs_nudge:{row.scheme_id}", wanted)
        if row.status == "applied":
            due = (row.status_changed_at or utcnow()).date() + timedelta(days=30)
            _want(db, st, row, "result_check", max(due, today),
                  f"Did you hear back about {name}? Update your tracker in My schemes.",
                  f"result_check:{row.scheme_id}", wanted)
        if st.remind_renew and row.renewal_needed and row.renewal_date:
            due = row.renewal_date - timedelta(days=30)
            if due >= today:
                _want(db, st, row, "renewal_30", due,
                      f"🔁 Renewal for {name} is due on {row.renewal_date:%d %b %Y}. "
                      "Are you now in the next class or year? Reply EDIT to update your answers.",
                      f"renewal_30:{row.scheme_id}:{row.renewal_date}", wanted)
    db.flush()
    for r in db.execute(select(Reminder).where(Reminder.student_id == st.id, Reminder.status == "PENDING")).scalars():
        if r.kind != "new_schemes" and r.dedupe_key not in wanted:
            r.status, r.channel_status = "SKIPPED", "no longer applies (status/date/preference changed)"
    db.flush()


def _deliver(st: Student, text: str) -> str:
    """Free text inside WhatsApp's 24-hour window, otherwise the approved template if configured.
    Integration later: a Meta-approved utility template is needed for reminders outside the 24-hour window."""
    from .channels import whatsapp as wa
    within = st.last_inbound_at is not None and utcnow() - st.last_inbound_at < timedelta(hours=23, minutes=30)
    if within:
        return wa.send_text(st.wa_id, text)[0]
    if settings.reminder_template:
        return wa.send_template(st.wa_id, settings.reminder_template, settings.reminder_template_lang, [text[:900]])[0]
    return "not_sent: outside the 24-hour window and WHATSAPP_REMINDER_TEMPLATE is not set (integration later)"


def run_reminders(db: DB, today: date | None = None, dry_run: bool = False) -> dict:
    """Send due reminders + new-scheme alerts. Call daily (e.g. Render cron / external scheduler)."""
    today = today or _today()
    out = {"date": today.isoformat(), "sent": 0, "not_sent": 0, "skipped": 0, "new_scheme_alerts": 0, "dry_run": dry_run}
    students = db.execute(select(Student).where(Student.status == "ACTIVE")).scalars().all()
    eng = get_engine()
    for st in students:
        plan_reminders(db, st, today)
        if st.remind_new and st.answers:
            ids = [c["scheme_id"] for c in eng.evaluate(st.answers)["schemes"]]
            new = [i for i in ids if i not in set(st.seen_scheme_ids or [])]
            if new:
                names = ", ".join(eng.by_id[i].Scheme_Name for i in new[:3] if i in eng.by_id)
                _want(db, st, None, "new_schemes", today,
                      f"🆕 {len(new)} new scholarship(s) match your answers: {names}. Reply MY SCHEMES to see them.",
                      f"new_schemes:{today}", set())
                if not dry_run:
                    st.seen_scheme_ids = list(dict.fromkeys(list(st.seen_scheme_ids or []) + new))
                out["new_scheme_alerts"] += 1
        db.flush()
        due = db.execute(select(Reminder).where(Reminder.student_id == st.id, Reminder.status == "PENDING",
                                                Reminder.due_on <= today)).scalars().all()
        for r in due:
            if dry_run:
                continue
            status = _deliver(st, r.message or "")
            r.channel_status = status[:200]
            if status.startswith("accepted"):
                r.status, r.sent_at = "SENT", utcnow()
                out["sent"] += 1
            else:
                r.status = "NOT_SENT"
                out["not_sent"] += 1
    db.flush()
    return out


# ------------------------------------------------------------------ WhatsApp side of the codes
def wa_bot_link(db: DB, text: str) -> Optional[str]:
    return A.wa_link(db, text)


def handle_wa_code(db: DB, wa_id: str, text: str) -> Optional[dict]:
    """A SAVE-/OK- code sent from WhatsApp. Returns {"key": text key, "kw": {...}} or None if no code."""
    m = CODE_RE.search(text or "")
    if not m:
        return None
    kind = "SAVE_CONFIRM" if m.group(1).upper() == "SAVE" else "PARENT_OK"
    lc = find_code(db, f"{m.group(1).upper()}-{m.group(2).upper()}", kind)
    if not code_usable(lc):
        return {"key": "save_bad", "kw": {}}
    s = db.get(ChatSession, lc.session_id) if lc.session_id else None
    p = lc.payload or {}
    if kind == "SAVE_CONFIRM":
        st = upsert_student(db, wa_id, s, age_band=p.get("age_band") or "18plus", remind=p.get("remind"))
    else:                                            # parent confirms for an under-18 student
        child = p.get("child_wa_id")
        if not child:
            return {"key": "save_bad", "kw": {}}
        st = upsert_student(db, child, s, age_band="u18", parent_wa_id=wa_id, remind=p.get("remind"))
    rows = save_schemes(db, st, p.get("scheme_ids") or [])
    lc.used_at, lc.student_id = utcnow(), st.id
    lc.payload = dict(p, confirmed_by=wa_id[-4:])
    st.last_inbound_at = utcnow() if kind == "SAVE_CONFIRM" else st.last_inbound_at
    db.flush()
    if kind == "PARENT_OK":
        return {"key": "parent_ok", "kw": {}, "student": st}
    my = web_link_url(db, s, "my") if s is not None and s.wa_id == wa_id else \
        f"{settings.public_base_url}/companion?c=" + new_code(db, "WEB_LINK", wa_id=wa_id, student_id=st.id,
                                                              payload={"screen": "my"}).code
    return {"key": "save_ok", "kw": {"n": len(rows), "url": my}, "student": st}


def save_wa_text(code: str) -> str:
    return f"Hi, please save my scholarships. Code {code}"


def parent_wa_text(code: str) -> str:
    return f"YES, I allow scholarship reminders for my child. Code {code}"


def parent_share_message(db: DB, code: str) -> dict:
    link = A.wa_link(db, parent_wa_text(code))
    msg = ("Namaste! I found government scholarships I can apply for. To get last-date reminders on WhatsApp I need "
           f"your OK (I am under 18). Please tap this link and send the message: {link or parent_wa_text(code)}")
    return {"bot_link": link, "message": msg, "whatsapp_share_url": "https://wa.me/?text=" + quote(msg)}
