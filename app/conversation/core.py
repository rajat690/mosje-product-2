"""Channel-agnostic conversation engine.

The engine knows nothing about WhatsApp or the web. It takes a text input for a session and
returns a structured BotReply (text + quick-reply options + scheme cards). Channel adapters
(app/channels/whatsapp.py, app/channels/web.py) turn that into a WhatsApp text or JSON.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import asdict, dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .. import attribution as A
from .. import facts as F
from ..config import settings
from ..db import ChatSession, Message, Referral, Suggestion, utcnow
from ..eligibility import get_engine
from .texts import t

# ------------------------------------------------------------------ reply object
@dataclass
class BotReply:
    text: str
    options: list = field(default_factory=list)      # [{"id": "1", "label": "..."}]
    cards: list = field(default_factory=list)        # scheme cards
    footer: str = ""                                 # shown after the cards (disclaimer)
    state: str = ""
    status: str = "ACTIVE"
    language: str = "en"
    input_hint: str = "choice"                       # choice | text | none
    events: list = field(default_factory=list)       # e.g. ["completed"], ["opted_out"]
    silent: bool = False                             # True -> send nothing (e.g. after STOP)
    share: dict | None = None                        # personal share links after feedback

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("events")
        d.pop("silent")
        return d


# ------------------------------------------------------------------ commands
def _clean(text: str) -> str:
    return re.sub(r"[\s!.,;:]+$", "", re.sub(r"\s+", " ", (text or "").strip().lower()))


GREET = {"hi", "hii", "hello", "hey", "namaste", "namaskar", "start", "menu", "नमस्ते", "हाय", "हेलो",
         "find scholarships for me", "मेरे लिए छात्रवृत्ति खोजें"}
RESTART = {"restart", "reset", "start again", "फिर से शुरू करें", "फिर से"}
HELP = {"help", "?", "मदद", "सहायता"}
STOP = {"stop", "unsubscribe", "बंद", "रोकें"}
MORE = {"more", "और", "next"}
SKIP = {"skip", "छोड़ें", "छोड़े"}


def is_greeting(text: str) -> bool:
    return _clean(text) in GREET | RESTART


# ------------------------------------------------------------------ questions
INCOME_BANDS = [100000, 250000, 350000, 450000, 800000, 800001]


def question_options(key: str, lang: str) -> list[dict]:
    if key == "class_passed":
        return [{"id": "1", "label": t(lang, "o_class_X"), "value": "X"},
                {"id": "2", "label": t(lang, "o_class_XII"), "value": "XII"},
                {"id": "3", "label": t(lang, "o_class_other"), "value": "OTHER"}]
    if key == "state":
        return [{"id": str(i), "label": s, "value": s} for i, s in enumerate(F.states(), start=1)]
    if key == "category":
        return [{"id": str(i), "label": t(lang, f"cat_{c}") if c in ("General", "Minority") else c, "value": c}
                for i, c in enumerate(F.CATEGORIES, start=1)]
    if key == "gender":
        return [{"id": str(i), "label": t(lang, f"g_{g}"), "value": g} for i, g in enumerate(F.GENDERS, start=1)]
    if key == "annual_family_income":
        opts = [{"id": str(i), "label": t(lang, f"inc_{b}"), "value": b} for i, b in enumerate(INCOME_BANDS, start=1)]
        opts.append({"id": str(len(opts) + 1), "label": t(lang, "o_dont_know"), "value": None})
        return opts
    if key == "dob":
        return [{"id": "1", "label": t(lang, "o_skip"), "value": None}]
    return []


NORMALISERS = {"class_passed": F.norm_class, "state": F.norm_state, "category": F.norm_category,
               "gender": F.norm_gender, "annual_family_income": F.norm_income, "dob": F.norm_dob}

MISSING = object()


def parse_answer(key: str, text: str, lang: str):
    """Return the normalised value, None for an explicit 'don't know/skip', or MISSING if invalid."""
    raw = (text or "").strip()
    low = _clean(raw)
    opts = question_options(key, lang)
    for o in opts:
        if low == o["id"] or low == o["label"].lower() or (isinstance(o["value"], str) and low == o["value"].lower()):
            return o["value"]
    if key == "dob" and low in SKIP:
        return None
    if key == "annual_family_income" and low in {"don't know", "dont know", "पता नहीं"}:
        return None
    v = NORMALISERS[key](raw)
    return MISSING if v is None else v


def inr(v: int) -> str:
    """Indian digit grouping: 250000 -> ₹2,50,000."""
    s = str(int(v))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups) + "," + tail


def fmt_fact(key: str, v, lang: str) -> str:
    if v is None:
        return t(lang, "o_dont_know")
    if key == "annual_family_income":
        if v in INCOME_BANDS:
            return t(lang, f"inc_{v}")
        return inr(v)
    if key == "class_passed":
        return {"X": "Class 10", "XII": "Class 12"}.get(v, str(v)) if lang == "en" else {"X": "कक्षा 10", "XII": "कक्षा 12"}.get(v, str(v))
    if key == "gender":
        return t(lang, f"g_{v}")
    if key == "category" and v in ("General", "Minority"):
        return t(lang, f"cat_{v}")
    return str(v)


def facts_block(facts: dict, lang: str, keys: list[str]) -> str:
    return "\n".join(f"• {t(lang, 'f_' + k)}: {fmt_fact(k, facts[k], lang)}" for k in keys if k in facts)


# ------------------------------------------------------------------ session helpers
def new_public_id() -> str:
    return "s_" + secrets.token_urlsafe(12)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def log_message(db: DB, session: Optional[ChatSession], direction: str, body: str, *, channel: str,
                external_id: str | None = None, status: str | None = None) -> Message:
    m = Message(session_id=session.id if session else None, channel=channel, direction=direction,
                body=body or "", external_id=external_id, status=status)
    db.add(m)
    db.flush()
    return m


def find_referral_for_mobile(db: DB, mobile: str, source_system: str | None = None) -> Optional[Referral]:
    q = select(Referral).where(Referral.mobile == mobile)
    if source_system:
        q = q.where(Referral.source_system == source_system)
    return db.execute(q.order_by(Referral.created_at.desc(), Referral.id.desc()).limit(1)).scalar_one_or_none()


def latest_session_for_wa(db: DB, wa_id: str) -> Optional[ChatSession]:
    return db.execute(select(ChatSession).where(ChatSession.channel == "whatsapp", ChatSession.wa_id == wa_id,
                                                ChatSession.status != "RESTARTED")
                      .order_by(ChatSession.id.desc()).limit(1)).scalar_one_or_none()


def _needed() -> list[str]:
    return get_engine().needed_facts()


def start_session(db: DB, *, channel: str, wa_id: str | None = None, referral: Referral | None = None,
                  source_system: str | None = None, language: str | None = None,
                  token_hash: str | None = None, attribution: "A.Attribution | None" = None,
                  inherit_from: ChatSession | None = None, greet_lang: str | None = None) -> tuple[ChatSession, BotReply]:
    if referral is None and attribution is not None and attribution.referral is not None:
        referral = attribution.referral          # per-recipient outreach link -> that referral
    prefilled = {}
    first = None
    if referral is not None:
        prefilled = {k: v for k, v in (referral.facts or {}).items() if k in _needed()}
        first = referral.first_name
        language = language or referral.language
        source_system = referral.source_system
    lang = language if language in ("en", "hi") else (greet_lang if greet_lang in ("en", "hi") else "en")
    s = ChatSession(public_id=new_public_id(), channel=channel, wa_id=wa_id, token_hash=token_hash,
                    source_system=source_system, referral_id=referral.id if referral else None,
                    language=lang, answers={}, prefilled=prefilled, state="NEW", status="ACTIVE")
    if language in ("en", "hi"):
        s.answers = {"_lang_done": True}
    if inherit_from is not None:
        A.inherit(s, inherit_from)
    else:
        A.apply(s, attribution or A.Attribution(first_touch={"channel": channel, "at": utcnow().isoformat() + "Z"}))
    db.add(s)
    db.flush()
    if referral is not None:
        referral.status = "IN_CONVERSATION"
        referral.last_session_id = s.id
        referral.updated_at = utcnow()
    greet = t(lang, "welcome_named", name=first) if first else t(lang, "welcome")
    reply = _advance(db, s)
    reply.text = f"{greet}\n{t(lang, 'intro')}\n\n{reply.text}"
    return s, reply


def _set_answers(s: ChatSession, **kv):
    a = dict(s.answers or {})
    a.update(kv)
    s.answers = a          # reassign so SQLAlchemy notices the JSON change


def public_answers(s: ChatSession) -> dict:
    return {k: v for k, v in (s.answers or {}).items() if not k.startswith("_")}


def _ask(s: ChatSession, key: str, prefix: str = "") -> BotReply:
    lang = s.language
    s.state = f"ASK_{key}"
    text = t(lang, f"q_{key}")
    if prefix:
        text = f"{prefix}\n\n{text}"
    return BotReply(text=text, options=[{"id": o["id"], "label": o["label"]} for o in question_options(key, lang)],
                    state=s.state, language=lang, input_hint="text" if key in ("dob", "annual_family_income", "state") else "choice")


def _advance(db: DB, s: ChatSession, prefix: str = "") -> BotReply:
    a = s.answers or {}
    lang = s.language
    if not a.get("_lang_done"):
        s.state = "LANG"
        return BotReply(text=(prefix + "\n\n" if prefix else "") + t(lang, "choose_lang"),
                        options=[{"id": "1", "label": "English"}, {"id": "2", "label": "हिंदी"}],
                        state=s.state, language=lang)
    if s.prefilled and not a.get("_prefill_done"):
        s.state = "CONFIRM_PREFILL"
        body = t(lang, "prefill", facts=facts_block(s.prefilled, lang, _needed()))
        return BotReply(text=(prefix + "\n\n" if prefix else "") + body,
                        options=[{"id": "1", "label": t(lang, "prefill_yes")}, {"id": "2", "label": t(lang, "prefill_no")}],
                        state=s.state, language=lang)
    for key in _needed():
        if key not in a:
            return _ask(s, key, prefix)
    return _finish(db, s)


def results_options(s: ChatSession, total: int) -> list[dict]:
    lang = s.language
    options = []
    if s.result_offset < total:
        options.append({"id": "1", "label": t(lang, "o_more")})
    if s.feedback_rating is None:
        options.append({"id": "2", "label": t(lang, "o_feedback")})
    options += [{"id": "3", "label": t(lang, "o_restart")}, {"id": "4", "label": t(lang, "o_help")}]
    return options


def _results_page(db: DB, s: ChatSession, start: int) -> BotReply:
    lang = s.language
    rows = db.execute(select(Suggestion).where(Suggestion.session_id == s.id).order_by(Suggestion.rank)).scalars().all()
    total = len(rows)
    n = settings.max_results
    page = rows[start:start + n]
    for r in page:
        r.shown = True
    s.result_offset = start + len(page)
    s.state = "RESULTS"
    options = results_options(s, total)
    if not page:
        text = t(lang, "results_none") if total == 0 else t(lang, "no_more")
        cards = []
    else:
        text = t(lang, "results_head", n=len(page), a=start + 1, b=start + len(page), total=total)
        cards = [{"rank": r.rank, "scheme_id": r.scheme_id, "name": r.scheme_name, "benefit": r.benefit or "",
                  "apply_url": r.apply_url or ""} for r in page]
    return BotReply(text=text, options=options, cards=cards, state=s.state, status=s.status, language=lang,
                    input_hint="choice")


def _finish(db: DB, s: ChatSession) -> BotReply:
    lang = s.language
    facts = public_answers(s)
    result = get_engine().evaluate(facts)
    db.query(Suggestion).filter(Suggestion.session_id == s.id).delete()
    for c in result["schemes"]:
        db.add(Suggestion(session_id=s.id, referral_id=s.referral_id, rank=c["rank"], scheme_id=c["scheme_id"],
                          scheme_name=c["name"][:300], benefit=(c["benefit"] or "")[:300], apply_url=(c["apply_url"] or "")[:500]))
    db.flush()
    s.eligible_count = result["eligible_count"]
    s.status = "COMPLETED"
    s.completed_at = utcnow()
    _set_answers(s, _rule_version=result["rule_version"], _as_of=result["as_of"])
    if s.referral_id:
        ref = db.get(Referral, s.referral_id)
        if ref:
            ref.status = "COMPLETED"
            ref.updated_at = utcnow()
    summary = t(lang, "summary", facts="; ".join(f"{t(lang, 'f_' + k)}: {fmt_fact(k, v, lang)}"
                                                 for k in _needed() for v in [facts.get(k, MISSING)] if v is not MISSING))
    reply = _results_page(db, s, 0)
    reply.text = f"{summary}\n\n{reply.text}"
    reply.footer = t(lang, "results_foot")
    reply.status = "COMPLETED"
    reply.events.append("completed")
    return reply


def _current_prompt(db: DB, s: ChatSession, prefix: str) -> BotReply:
    if s.state == "RESULTS":
        r = _results_page(db, s, max(0, s.result_offset - settings.max_results))
        r.text = f"{prefix}\n\n{r.text}"
        return r
    if s.state == "FEEDBACK_RATING":
        r = _ask_rating(s)
        r.text = f"{prefix}\n\n{r.text}"
        return r
    if s.state == "FEEDBACK_COMMENT":
        return BotReply(text=f"{prefix}\n\n{t(s.language, 'q_comment')}", options=[{"id": "0", "label": t(s.language, "o_skip")}],
                        state=s.state, status=s.status, language=s.language, input_hint="text")
    if s.state == "ENDED":
        return BotReply(text=prefix, state=s.state, status=s.status, language=s.language, input_hint="text")
    return _advance(db, s, prefix)


def _ask_rating(s: ChatSession) -> BotReply:
    s.state = "FEEDBACK_RATING"
    return BotReply(text=t(s.language, "q_rating"), options=[{"id": str(i), "label": "⭐" * i} for i in range(1, 6)],
                    state=s.state, status=s.status, language=s.language)


def restart(db: DB, s: ChatSession) -> tuple[ChatSession, BotReply]:
    if s.status == "ACTIVE":
        s.status = "RESTARTED"
    ref = db.get(Referral, s.referral_id) if s.referral_id else None
    return start_session(db, channel=s.channel, wa_id=s.wa_id, referral=ref, source_system=s.source_system,
                         token_hash=s.token_hash, inherit_from=s, greet_lang=s.language)


def handle_message(db: DB, s: ChatSession, text: str) -> tuple[ChatSession, BotReply]:
    """Process one user input for session s. May return a NEW session (after hi/restart)."""
    low = _clean(text)
    lang = s.language
    s.updated_at = utcnow()

    if low in GREET | RESTART:
        return restart(db, s)
    if low in STOP:
        s.status = "OPTED_OUT"
        s.state = "ENDED"
        if s.referral_id:
            ref = db.get(Referral, s.referral_id)
            if ref:
                ref.status = "OPTED_OUT"
                ref.updated_at = utcnow()
        return s, BotReply(text=t(lang, "stopped"), state=s.state, status=s.status, language=lang,
                           input_hint="text", events=["opted_out"])
    if s.status == "OPTED_OUT":
        return s, BotReply(text="", state=s.state, status=s.status, language=lang, silent=True)
    if low in HELP:
        return s, _current_prompt(db, s, t(lang, "help"))

    state = s.state
    if state == "LANG":
        if low in {"1", "english", "en", "eng"}:
            s.language = "en"
        elif low in {"2", "hindi", "hi", "हिंदी", "हिन्दी"}:
            s.language = "hi"
        else:
            return s, _advance(db, s, t(lang, "invalid"))
        _set_answers(s, _lang_done=True)
        return s, _advance(db, s)

    if state == "CONFIRM_PREFILL":
        if low in {"1", "yes", "y", "haan", "हाँ", "हां", t(lang, "prefill_yes").lower()}:
            _set_answers(s, _prefill_done=True, _prefill_used=True, **s.prefilled)
        elif low in {"2", "no", "n", "nahi", "नहीं", t(lang, "prefill_no").lower()}:
            _set_answers(s, _prefill_done=True, _prefill_used=False)
        else:
            return s, _advance(db, s, t(lang, "invalid"))
        return s, _advance(db, s)

    if state.startswith("ASK_"):
        key = state[4:]
        v = parse_answer(key, text, lang)
        if v is MISSING:
            return s, _ask(s, key, t(lang, "invalid_dob" if key == "dob" else "invalid"))
        if key == "class_passed" and v == "OTHER":
            _set_answers(s, class_passed="OTHER")
            s.state = "ENDED"
            s.status = "COMPLETED"
            s.completed_at = utcnow()
            s.eligible_count = 0
            if s.referral_id:
                ref = db.get(Referral, s.referral_id)
                if ref:
                    ref.status = "COMPLETED"
                    ref.updated_at = utcnow()
            return s, BotReply(text=t(lang, "class_other"), state=s.state, status=s.status, language=lang,
                               input_hint="text", events=["completed"])
        _set_answers(s, **{key: v})
        return s, _advance(db, s)

    if state == "RESULTS":
        if low in {"1"} | MORE:
            return s, _results_page(db, s, s.result_offset)
        if low in {"2", "feedback", "rate", "share"}:
            return s, _ask_rating(s)
        if low in {"3"}:
            return restart(db, s)
        if low in {"4"}:
            return s, _current_prompt(db, s, t(lang, "help"))
        return s, _current_prompt(db, s, t(lang, "invalid"))

    if state == "FEEDBACK_RATING":
        if low in {"1", "2", "3", "4", "5"}:
            s.feedback_rating = int(low)
            s.state = "FEEDBACK_COMMENT"
            return s, BotReply(text=t(lang, "q_comment"), options=[{"id": "0", "label": t(lang, "o_skip")}],
                               state=s.state, status=s.status, language=lang, input_hint="text")
        r = _ask_rating(s)
        r.text = t(lang, "invalid") + "\n\n" + r.text
        return s, r

    if state == "FEEDBACK_COMMENT":
        if low not in SKIP | {"0"}:
            s.feedback_comment = text.strip()[:500]
        links = A.share_links(db, s)
        page = _results_page(db, s, max(0, s.result_offset - settings.max_results))
        share = t(lang, "share", wa=links["whatsapp_link"] or t(lang, "share_no_wa"), web=links["web_link"],
                  code=links["share_code"])
        return s, BotReply(text=share, options=page.options, state="RESULTS", status=s.status, language=lang,
                           events=["feedback"], share=links)

    if state == "ENDED":
        return s, BotReply(text=t(lang, "help"), state=s.state, status=s.status, language=lang, input_hint="text")

    return s, _advance(db, s)


# ------------------------------------------------------------------ plain-text rendering (WhatsApp, SMS, logs)
def render_text(r: BotReply, limit: int = 4000) -> str:
    lang = r.language
    parts = [r.text]
    for c in r.cards:
        lines = [f"*{c['rank']}. {c['name']}*"]
        if c.get("benefit"):
            lines.append(f"{t(lang, 'benefit')}: {c['benefit']}")
        if c.get("apply_url"):
            lines.append(f"{t(lang, 'apply')}: {c['apply_url']}")
        parts.append("\n".join(lines))
    if r.footer:
        parts.append(r.footer)
    if r.options:
        parts.append(t(lang, "reply_number") + "\n" + "\n".join(f"{o['id']}. {o['label']}" for o in r.options))
    out = "\n\n".join(p for p in parts if p)
    return out if len(out) <= limit else out[: limit - 1] + "…"
