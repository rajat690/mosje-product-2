"""Database: SQLAlchemy 2.x, Postgres in production (DATABASE_URL), SQLite locally/tests."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, create_engine, event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)   # stored as naive UTC


def normalise_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Base(DeclarativeBase):
    pass


class SourceSystem(Base):
    __tablename__ = "p2_source_systems"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    callback_url: Mapped[Optional[str]] = mapped_column(String(500))
    callback_secret: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class OutreachMessage(Base):
    """An outreach message/campaign sent by a Product 1 (registered so clicks can be attributed)."""
    __tablename__ = "p2_outreach_messages"
    __table_args__ = (UniqueConstraint("source_system", "message_id", name="uq_outreach_source_msg"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_system: Mapped[str] = mapped_column(String(64), index=True)
    message_id: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)       # OM-XXXXXX (public, in links)
    campaign: Mapped[Optional[str]] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")          # whatsapp | sms | email
    template_text: Mapped[Optional[str]] = mapped_column(Text)
    template_version: Mapped[Optional[str]] = mapped_column(String(50))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OutreachRecipient(Base):
    """Optional per-recipient link code for an outreach message (opaque; no PII in links)."""
    __tablename__ = "p2_outreach_recipients"
    __table_args__ = (UniqueConstraint("outreach_id", "recipient_ref", name="uq_outreach_recipient"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outreach_id: Mapped[int] = mapped_column(ForeignKey("p2_outreach_messages.id"), index=True)
    recipient_ref: Mapped[str] = mapped_column(String(100))          # usually the referral external_ref
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)   # RXXXXXXXX
    referral_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KV(Base):
    """Tiny key/value store (e.g. the WhatsApp display number learned from webhooks)."""
    __tablename__ = "p2_kv"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Referral(Base):
    __tablename__ = "p2_referrals"
    __table_args__ = (UniqueConstraint("source_system", "external_ref", name="uq_referral_source_ref"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_system: Mapped[str] = mapped_column(String(64), index=True)
    external_ref: Mapped[str] = mapped_column(String(100))
    mobile: Mapped[Optional[str]] = mapped_column(String(20), index=True)   # digits, with country code
    name: Mapped[Optional[str]] = mapped_column(String(200))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    facts: Mapped[dict] = mapped_column(JSON, default=dict)       # normalised known facts
    reason: Mapped[Optional[str]] = mapped_column(String(50))
    language: Mapped[Optional[str]] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", index=True)
    invite_status: Mapped[Optional[str]] = mapped_column(String(200))
    last_session_id: Mapped[Optional[int]] = mapped_column(Integer)
    callback_status: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ChatSession(Base):
    __tablename__ = "p2_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp", index=True)   # whatsapp | web
    wa_id: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    token_hash: Mapped[Optional[str]] = mapped_column(String(64))
    source_system: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    referral_id: Mapped[Optional[int]] = mapped_column(ForeignKey("p2_referrals.id"))
    state: Mapped[str] = mapped_column(String(40), default="NEW")
    language: Mapped[str] = mapped_column(String(5), default="en")
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    prefilled: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE COMPLETED RESTARTED OPTED_OUT
    result_offset: Mapped[int] = mapped_column(Integer, default=0)
    last_reply: Mapped[Optional[dict]] = mapped_column(JSON)    # web channel: last BotReply (to resume a widget)
    # --- entry-source attribution (first touch) ---
    entry_source: Mapped[str] = mapped_column(String(20), default="ORGANIC", index=True)  # OUTREACH | ORGANIC | PEER_REFERRAL
    first_touch: Mapped[Optional[dict]] = mapped_column(JSON)    # raw codes / params / utm, timestamp
    outreach_id: Mapped[Optional[int]] = mapped_column(ForeignKey("p2_outreach_messages.id"), index=True)
    outreach_recipient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("p2_outreach_recipients.id"))
    referrer_session_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    share_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True)   # this user's REF-xxxx code
    feedback_rating: Mapped[Optional[int]] = mapped_column(Integer)
    feedback_comment: Mapped[Optional[str]] = mapped_column(String(500))
    # --- consent (Update 1): AGREED | DECLINED | NULL (not asked yet); time in UTC; version of the notice shown
    consent_status: Mapped[Optional[str]] = mapped_column(String(20))
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    consent_version: Mapped[Optional[str]] = mapped_column(String(40))
    eligible_count: Mapped[Optional[int]] = mapped_column(Integer)
    # --- Update 3: link to a saved student profile ("Save on WhatsApp") and the one-time link it came from
    student_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    opened_via: Mapped[Optional[str]] = mapped_column(String(20))     # one_time_link | direct | embed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Message(Base):
    __tablename__ = "p2_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("p2_sessions.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    direction: Mapped[str] = mapped_column(String(3))     # in | out
    external_id: Mapped[Optional[str]] = mapped_column(String(128), unique=True)  # WhatsApp message id
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[Optional[str]] = mapped_column(String(200))    # sent/delivered/read/failed/not_sent...
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Suggestion(Base):
    __tablename__ = "p2_suggestions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("p2_sessions.id"), index=True)
    referral_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    rank: Mapped[int] = mapped_column(Integer)
    scheme_id: Mapped[str] = mapped_column(String(20))
    scheme_name: Mapped[str] = mapped_column(String(300))
    benefit: Mapped[Optional[str]] = mapped_column(String(300))
    apply_url: Mapped[Optional[str]] = mapped_column(String(500))
    shown: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ------------------------------------------------------------------ Update 3: Save on WhatsApp, feedback, referrals
class Student(Base):
    """A student who chose "Save on WhatsApp" (opt-in). Only the number, language, the 5 answers, saved schemes,
    dates and alert settings are kept - never name, Aadhaar, bank details or documents."""
    __tablename__ = "p2_students"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    wa_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)          # digits with country code
    token_hash: Mapped[Optional[str]] = mapped_column(String(64))                    # student (My schemes) token
    language: Mapped[str] = mapped_column(String(5), default="en")
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    age_band: Mapped[Optional[str]] = mapped_column(String(10))                     # 18plus | u18
    parent_wa_id: Mapped[Optional[str]] = mapped_column(String(20))                 # under-18: parent who confirmed
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)    # ACTIVE | STOPPED
    remind_deadline: Mapped[bool] = mapped_column(Boolean, default=True)
    remind_new: Mapped[bool] = mapped_column(Boolean, default=True)
    remind_renew: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_text_version: Mapped[Optional[str]] = mapped_column(String(40))
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    entry_source: Mapped[Optional[str]] = mapped_column(String(20))
    source_system: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    first_session_id: Mapped[Optional[int]] = mapped_column(Integer)
    share_code: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    seen_scheme_ids: Mapped[list] = mapped_column(JSON, default=list)              # for new-scheme alerts
    last_inbound_at: Mapped[Optional[datetime]] = mapped_column(DateTime)            # WhatsApp 24-hour window
    last_alert_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SavedScheme(Base):
    """Application tracker row: Saved / Documents pending / Applied / Result / Approved / Rejected."""
    __tablename__ = "p2_saved_schemes"
    __table_args__ = (UniqueConstraint("student_id", "scheme_id", name="uq_saved_student_scheme"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("p2_students.id"), index=True)
    scheme_id: Mapped[str] = mapped_column(String(20))
    scheme_name: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="saved")    # saved docs applied result approved rejected
    docs_have: Mapped[dict] = mapped_column(JSON, default=dict)         # {"aadhaar": true, ...}
    last_date: Mapped[Optional[date]] = mapped_column(Date)             # from scheme data or entered by the student
    renewal_needed: Mapped[Optional[bool]] = mapped_column(Boolean)
    renewal_date: Mapped[Optional[date]] = mapped_column(Date)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LinkCode(Base):
    """One-time, expiring codes.

    WEB_LINK      WhatsApp -> web: link /companion?c=<code> sent by the bot (tied to the phone, never shows it)
    SAVE_CONFIRM  web -> WhatsApp: the student sends "Hi ... Code SAVE-XXXX" from WhatsApp (proves the number, no OTP)
    PARENT_OK     under 18: a parent sends "YES ... Code OK-XXXX" from WhatsApp before anything is stored
    """
    __tablename__ = "p2_link_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    wa_id: Mapped[Optional[str]] = mapped_column(String(20))
    session_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Reminder(Base):
    """A reminder / alert for a saved student. Sent by POST /v1/jobs/run-reminders (schedule it with a cron)."""
    __tablename__ = "p2_reminders"
    __table_args__ = (UniqueConstraint("student_id", "dedupe_key", name="uq_reminder_dedupe"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("p2_students.id"), index=True)
    saved_id: Mapped[Optional[int]] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))       # deadline_7 deadline_2 result_check renewal_30 new_schemes docs_nudge
    dedupe_key: Mapped[str] = mapped_column(String(120))
    due_on: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)  # PENDING SENT SKIPPED NOT_SENT
    channel_status: Mapped[Optional[str]] = mapped_column(String(200))
    message: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Feedback(Base):
    """Rating (1-5) + optional comment + context, from the web companion or WhatsApp."""
    __tablename__ = "p2_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    source_system: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(String(1000))
    context: Mapped[dict] = mapped_column(JSON, default=dict)      # {"screen": "summary", "scheme_id": ..., ...}
    language: Mapped[Optional[str]] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ShareEvent(Base):
    """'Refer a friend' / share actions (the REF code itself lives on the session: ChatSession.share_code)."""
    __tablename__ = "p2_share_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_code: Mapped[str] = mapped_column(String(20), index=True)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30), default="refer")      # refer | scheme | parent
    via: Mapped[Optional[str]] = mapped_column(String(30))              # whatsapp | copy | native | email
    scheme_id: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Event(Base):
    """Funnel events from the web companion: web_opened, questions_done, scheme_viewed, apply_clicked, saved, shared,
    listen, mic ... (per session; joined to the outreach message through the session's attribution)."""
    __tablename__ = "p2_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(40), index=True)
    scheme_id: Mapped[Optional[str]] = mapped_column(String(20))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ProcessedEvent(Base):
    """Idempotency: one row per inbound WhatsApp message id."""
    __tablename__ = "p2_processed_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


engine = None
SessionLocal = None


def init_engine(url: str | None = None):
    global engine, SessionLocal
    url = normalise_db_url(url or settings.database_url)
    kwargs = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            from sqlalchemy.pool import StaticPool
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)          # creates missing TABLES only (never alters or drops)
    ensure_schema(engine)                     # adds missing COLUMNS to existing tables
    return engine


def ensure_schema(eng) -> list[str]:
    """Safe, additive schema upgrade for an existing database (e.g. the live Neon DB).

    create_all() never changes a table that already exists, so a column added to a model in a
    later update would be missing on the old database. This adds any such column as NULLable with
    ALTER TABLE ... ADD COLUMN (no defaults rewritten, nothing dropped, no data touched).
    Returns the list of statements that were run (empty when the schema is already current).
    """
    from sqlalchemy import inspect, text
    insp = inspect(eng)
    done = []
    existing_tables = set(insp.get_table_names())
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have or col.primary_key:
                    continue
                ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(dialect=eng.dialect)}'
                conn.execute(text(ddl))
                done.append(ddl)
    if done:
        import logging
        logging.getLogger(__name__).warning("Schema upgraded: %s", "; ".join(done))
    return done


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
