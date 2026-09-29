"""Channel-agnostic conversation engine.

The engine knows nothing about WhatsApp or the web. It takes a text input for a session and
returns a structured BotReply (text + options + scheme cards + detail card). Channel adapters
(app/channels/whatsapp.py, app/channels/web.py) turn that into WhatsApp interactive messages / JSON.

Update 1 (29 Sep 2026): language first (alphabetical), consent (Agree / Don't agree), at most 5
questions (education level, gender, monthly family income and social category as in the SETU chatbot,
State/UT), summary (Proceed / Edit details), scheme list + detail cards (short Description / Eligibility /
Documents / Application URL), Go back / Main menu everywhere, Share scheme (peer-referral links),
Share feedback (1-5 stars), friendly fallback + "why am I seeing this" handling, 14 languages.

Views ("_view" in the session answers, previous views in "_hist"):
    LANG, CONSENT, DECLINED, MENU, ASK_<fact>, SUMMARY, RESULTS:<offset>, DETAIL:<rank>, SHARE:<rank>,
    WHY, FEEDBACK_RATING, FEEDBACK_COMMENT, SHARED, ENDED
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
from ..eligibility.engine import check_groups_open, profile_from_facts, scheme_detail, short_benefit
from .texts import LANG_CODES, LANG_ORDER, LANGS, lang_label, t

HIST_MAX = 30


# ------------------------------------------------------------------ reply object
@dataclass
class BotReply:
    text: str
    options: list = field(default_factory=list)      # [{"id": "1", "label": "...", "kind": "item|nav", "desc": ""}]
    cards: list = field(default_factory=list)        # scheme list cards
    footer: str = ""                                 # shown after the cards (disclaimer)
    state: str = ""
    status: str = "ACTIVE"
    language: str = "en"
    input_hint: str = "choice"                       # choice | text | none
    events: list = field(default_factory=list)       # e.g. ["completed"], ["opted_out"]
    silent: bool = False                             # True -> send nothing (e.g. after STOP)
    share: dict | None = None                        # personal share links after feedback
    detail: dict | None = None                       # structured scheme detail card (web)
    view: str = ""                                   # view token (for adapters / debugging)
    section_label: str = ""                          # heading shown before 'check eligibility' cards
    ui: dict | None = None                           # extra web labels (e.g. language dropdown "Continue")

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("events")
        d.pop("silent")
        return d


def item(i, label, desc: str = "") -> dict:
    d = {"id": str(i), "label": label, "kind": "item"}
    if desc:
        d["desc"] = desc
    return d


def nav(i, lang, key) -> dict:
    return {"id": i, "label": t(lang, key), "kind": "nav"}


# ------------------------------------------------------------------ commands
def _clean(text: str) -> str:
    return re.sub(r"[\s!.,;:]+$", "", re.sub(r"\s+", " ", (text or "").strip().lower()))


GREET = {"hi", "hii", "hello", "hey", "namaste", "namaskar", "start", "नमस्ते", "हाय", "हेलो",
         "find scholarships for me", "मेरे लिए छात्रवृत्ति खोजें"}
RESTART = {"restart", "reset", "start again", "फिर से शुरू करें", "फिर से"}
HELP = {"help", "?", "मदद", "सहायता", "help me"}
STOP = {"stop", "unsubscribe", "बंद", "रोकें"}
MORE = {"more", "और", "next", "more schemes"}
SKIP = {"skip", "छोड़ें", "छोड़े"}
BACK = {"back", "go back", "previous", "पीछे", "वापस", "पीछे जाएँ"}
MENU = {"menu", "main menu", "मेनू", "मेन्यू", "मुख्य मेनू"}
LANGW = {"language", "lang", "languages", "भाषा", "change language"}
CHANGE = {"change", "change my answers", "edit", "बदलें"}

WHY_RX = re.compile(r"\bwhy\b|\bwrong\b|galat|incorrect|mistake|not (for )?me\b|showing me|\bnot eligible\b|"
                    r"क्यों|क्यूँ|गलत|ग़लत|কেন|ভুল|ಏಕೆ|ஏன்|ఎందుకు|എന്തുകൊണ്ട്|କାହିଁକି|કેમ|का\s|ਕਿਉਂ", re.I)
CAT_RX = [
    ("General", re.compile(r"\bgeneral\b|\bgen\b|\bopen\b|\bunreserved\b|सामान्य|जनरल|সাধারণ", re.I)),
    ("SC", re.compile(r"\bsc\b|scheduled caste|dalit|अनुसूचित जाति", re.I)),
    ("ST", re.compile(r"\bst\b|scheduled tribe|tribal|अनुसूचित जनजाति|आदिवासी", re.I)),
    ("OBC", re.compile(r"\bobc\b|backward|पिछड़ा|ओबीसी", re.I)),
    ("Minority", re.compile(r"minority|muslim|christian|sikh|parsi|jain|buddhist|अल्पसंख्यक", re.I)),
]
SELF_RX = re.compile(r"(?:\bi\s*am\b|\bi'?m\b|\bim\b|\bmain\b|\bmai\b|मैं|आमि|ami)\s+(?:\w+\s+){0,3}?"
                     r"(general|gen|open|unreserved|sc|st|obc|minority|muslim|christian|sikh|सामान्य|जनरल)", re.I)


def is_greeting(text: str) -> bool:
    return _clean(text) in GREET | RESTART


def mentioned_category(text: str) -> tuple[Optional[str], bool]:
    """(category the user says they belong to, whether any category word appears)."""
    m = SELF_RX.search(text or "")
    if m:
        w = m.group(1).lower()
        for cat, rx in CAT_RX:
            if rx.search(w):
                return cat, True
    found = [cat for cat, rx in CAT_RX if rx.search(text or "")]
    return (found[0] if len(found) == 1 else None), bool(found)


# ------------------------------------------------------------------ questions (max 5, Update 1 feedback 5)
# Education level -> answers.class_passed (kept for API compatibility): PRE X XII UG PG OTHER
EDU_LEVELS = ["PRE", "X", "XII", "UG", "PG", "OTHER"]
# SETU income bands (monthly household income, as in the SETU chatbot Rule Engine v4) -> annual range used by
# the V3.0 income check. A scheme ceiling inside a band is shown as 'check eligibility', never hidden.
INCOME_BANDS = [("m10k", None, 120000), ("m30k", 120001, 360000), ("gt30k", 360001, None)]
BAND = {b: (lo, hi) for b, lo, hi in INCOME_BANDS}
QUESTION_KEYS = ["state", "class_passed", "gender", "annual_family_income", "category"]   # Update 2: State first
ASK_GENDERS = ["Male", "Female"]
CONSENT_VERSION = "p2-consent-2026-09-29"
FACT_KEYS = QUESTION_KEYS + ["income_min", "income_band", "dob", "disability"]


def question_options(key: str, lang: str) -> list[dict]:
    if key == "class_passed":
        return [dict(item(i, t(lang, f"o_edu_{c}"), t(lang, f"edu_d_{c}")), value=c)
                for i, c in enumerate(EDU_LEVELS, start=1)]
    if key == "state":
        return [dict(item(i, s), value=s) for i, s in enumerate(F.states(), start=1)]
    if key == "category":
        return [dict(item(i, t(lang, f"cat_{c}")), value=c) for i, c in enumerate(F.CATEGORIES, start=1)]
    if key == "gender":
        return [dict(item(i, t(lang, f"g_{g}")), value=g) for i, g in enumerate(ASK_GENDERS, start=1)]
    if key == "annual_family_income":
        return [dict(item(i, t(lang, f"inc_{b}")), value=b) for i, (b, _, _) in enumerate(INCOME_BANDS, start=1)]
    return []


NORMALISERS = {"class_passed": F.norm_class, "state": F.norm_state, "category": F.norm_category,
               "gender": F.norm_gender, "annual_family_income": F.norm_income}

MISSING = object()


def parse_answer(key: str, text: str, lang: str):
    """Return the normalised value (income: a band code or an annual amount), or MISSING if invalid."""
    raw = (text or "").strip()
    low = _clean(raw)
    for lg in dict.fromkeys([lang, "en"]):
        for o in question_options(key, lg):
            if low == o["id"] or low == _clean(o["label"]) or (isinstance(o["value"], str) and low == o["value"].lower()):
                return o["value"]
    v = NORMALISERS[key](raw)
    if key == "annual_family_income" and v is not None:
        if not re.search(r"lakh|lac|\bl\b|लाख|year|annual|साल", low) and v < 100000:
            v *= 12                               # the question asks for MONTHLY income
    return MISSING if v is None else v


def income_facts(v) -> dict:
    """Stored facts for an income answer: band code -> annual upper bound + lower bound + band."""
    if isinstance(v, str) and v in BAND:
        lo, hi = BAND[v]
        return {"annual_family_income": hi, "income_min": lo, "income_band": v}
    return {"annual_family_income": v, "income_min": None, "income_band": None}


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


def fmt_fact(key: str, v, lang: str, facts: dict | None = None) -> str:
    facts = facts or {}
    if key == "disability":
        return t(lang, {True: "o_yes", False: "o_no"}.get(v, "o_prefer_not"))
    if key == "annual_family_income":
        band = facts.get("income_band")
        if band in BAND:
            return t(lang, "per_month", v=t(lang, f"inc_{band}"))
        return t(lang, "o_dont_know") if v is None else t(lang, "per_year", v=inr(v))
    if v is None:
        return t(lang, "o_dont_know")
    if key == "class_passed":
        return t(lang, f"cls_{v}") if v in EDU_LEVELS else str(v)
    if key == "gender":
        return t(lang, f"g_{v}")
    if key == "category":
        return t(lang, f"cat_{v}")
    return str(v)


def facts_block(facts: dict, lang: str, keys: list[str], mark: dict | None = None) -> str:
    mark = mark or {}
    return "\n".join(f"• {t(lang, 'f_' + k)}: {fmt_fact(k, facts[k], lang, facts)}" + (" 📁" if k in mark else "")
                     for k in keys if k in facts)


def facts_inline(facts: dict, lang: str) -> str:
    return "; ".join(f"{t(lang, 'f_' + k)}: {fmt_fact(k, facts[k], lang, facts)}" for k in _needed() if k in facts)


# ------------------------------------------------------------------ session helpers
def new_public_id() -> str:
    return "s_" + secrets.token_urlsafe(12)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def log_message(db: DB, session: Optional[ChatSession], direction: str, body: str, *, channel: str,
                external_id: str | None = None, status: str | None = None) -> Message:
    if session is not None and session.consent_status == "DECLINED" and direction == "in":
        body = "[not stored: consent declined]"          # no personal data after a 'Don't agree'
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


def latest_session_for_wa(db: DB, wa_id: str, include_restarted: bool = False) -> Optional[ChatSession]:
    q = select(ChatSession).where(ChatSession.channel == "whatsapp", ChatSession.wa_id == wa_id)
    if not include_restarted:
        q = q.where(ChatSession.status != "RESTARTED")
    return db.execute(q.order_by(ChatSession.id.desc()).limit(1)).scalar_one_or_none()


def chosen_language(s: Optional[ChatSession]) -> Optional[str]:
    """The language a returning user picked before (None if they never picked one)."""
    if s is not None and (s.answers or {}).get("_lang_done") and s.language in LANG_CODES:
        return s.language
    return None


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
        prefilled = {k: v for k, v in (referral.facts or {}).items() if k in _needed() or k == "disability"}
        first = referral.first_name
        language = language or referral.language
        source_system = referral.source_system
    language = language if language in LANG_CODES else None
    lang = language or (greet_lang if greet_lang in LANG_CODES else "en")
    s = ChatSession(public_id=new_public_id(), channel=channel, wa_id=wa_id, token_hash=token_hash,
                    source_system=source_system, referral_id=referral.id if referral else None,
                    language=lang, answers={}, prefilled=prefilled, state="NEW", status="ACTIVE")
    if language:
        s.answers = {"_lang_done": True, "_view": "LANG"}     # Back from the next step -> language list
    if inherit_from is not None and inherit_from.consent_status == "AGREED":
        s.consent_status, s.consent_at, s.consent_version = "AGREED", inherit_from.consent_at, inherit_from.consent_version
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


def _done(s: ChatSession) -> bool:
    return s.completed_at is not None and s.eligible_count is not None


# ------------------------------------------------------------------ view navigation
def _cur_view(s: ChatSession) -> str:
    return (s.answers or {}).get("_view") or ""


def _go(db: DB, s: ChatSession, token: str, prefix: str = "", push: bool = True) -> BotReply:
    a = dict(s.answers or {})
    cur = a.get("_view")
    hist = list(a.get("_hist") or [])
    if push and cur and cur != token and cur not in ("WHY", "SHARED"):
        hist.append(cur)
        hist = hist[-HIST_MAX:]
    a["_hist"], a["_view"] = hist, token
    s.answers = a
    r = _render(db, s, token)
    if prefix:
        r.text = f"{prefix}\n\n{r.text}" if r.text else prefix
    return r


def _back(db: DB, s: ChatSession) -> BotReply:
    a = dict(s.answers or {})
    hist = list(a.get("_hist") or [])
    cur = a.get("_view")
    while hist:
        tok = hist.pop()
        if tok != cur and _view_ok(db, s, tok):
            a["_hist"], a["_view"] = hist, tok
            s.answers = a
            return _render(db, s, tok)
    a["_hist"] = []
    s.answers = a
    return _go(db, s, cur or "MENU", t(s.language, "nothing_back"), push=False)


def _view_ok(db: DB, s: ChatSession, tok: str) -> bool:
    if tok.startswith(("RESULTS", "DETAIL", "SHARE")):
        return _done(s) and bool((s.answers or {}).get("_summary_ok"))
    if tok == "SUMMARY":
        return all(k in (s.answers or {}) for k in _needed()) and not (s.answers or {}).get("_summary_ok")
    if tok == "CONSENT":
        return s.consent_status != "AGREED"
    if tok.startswith(("FEEDBACK", "CONFIRM_PREFILL", "CHANGE", "DECLINED")):   # CONFIRM_PREFILL/CHANGE: pre-Update-1 history
        return False
    return bool(tok)


def _nav(s: ChatSession, *extra: str, menu: bool = True) -> list[dict]:
    """Standard navigation: [extra...] + Go back (if there is history) + Main menu."""
    lang = s.language
    out = []
    for e in extra:
        out.append(nav(e, lang, {"more": "o_more", "rate": "o_feedback", "change": "o_edit",
                                 "list": "o_back_list", "share": "o_share_scheme"}[e]))
    if (s.answers or {}).get("_hist"):
        out.append(nav("back", lang, "o_back"))
    if menu:
        out.append(nav("menu", lang, "o_menu"))
    return out


def _reply(s: ChatSession, text: str, options=None, **kw) -> BotReply:
    return BotReply(text=text, options=options or [], state=s.state, status=s.status, language=s.language,
                    view=_cur_view(s), **kw)


def _lang_options() -> list[dict]:
    """Language picker, alphabetical by English name (native script shown too)."""
    return [dict(item(i, lang_label(code)), code=code) for i, code in enumerate(LANG_ORDER, start=1)]


def _render(db: DB, s: ChatSession, tok: str) -> BotReply:
    lang = s.language
    a = s.answers or {}
    if tok == "LANG":
        s.state = "LANG"
        r = _reply(s, t(lang, "choose_lang"), _lang_options() + (_nav(s) if a.get("_lang_done") else []))
        r.ui = {"continue": t(lang, "lang_continue"), "dropdown": True}
        return r
    if tok == "CONSENT":
        s.state = "CONSENT"
        opts = [item("agree", t(lang, "o_agree")), item("disagree", t(lang, "o_disagree"))]
        if a.get("_hist"):
            opts.append(nav("back", lang, "o_back"))
        return _reply(s, t(lang, "consent"), opts)
    if tok == "DECLINED":
        s.state = "DECLINED"
        return _reply(s, t(lang, "consent_declined"), [item("agree", t(lang, "o_agree_now")), nav("lang", lang, "o_lang")],
                      input_hint="text")
    if tok == "MENU":
        s.state = "MENU"
        done = _done(s) and a.get("_summary_ok")
        opts = [nav("find", lang, "o_my_schemes" if done else "o_find")]
        if any(k in a for k in QUESTION_KEYS):
            opts.append(nav("change", lang, "o_edit"))
        opts += [nav("lang", lang, "o_lang"), nav("help", lang, "o_help")]
        if done and s.feedback_rating is None:
            opts.append(nav("rate", lang, "o_feedback"))
        if a.get("_hist"):
            opts.append(nav("back", lang, "o_back"))
        return _reply(s, t(lang, "menu_title"), opts)
    if tok.startswith("ASK_"):
        key = tok[4:]
        s.state = tok
        opts = [{k: v for k, v in o.items() if k != "value"} for o in question_options(key, lang)]
        n = _needed().index(key) + 1 if key in _needed() else 0
        text = (t(lang, "q_step", n=n, total=len(_needed())) + " " if n else "") + t(lang, f"q_{key}")
        prev = a if key in a else (a.get("_prev") or {})
        if key in prev:
            text += "\n" + t(lang, "current_answer", v=fmt_fact(key, prev[key], lang, prev))
        return _reply(s, text, opts + _nav(s), input_hint="text" if key in ("annual_family_income", "state") else "choice")
    if tok == "SUMMARY":
        s.state = "SUMMARY"
        facts = public_answers(s)
        pre = {k for k, v in (s.prefilled or {}).items() if facts.get(k) == v}
        body = t(lang, "summary_title", facts=facts_block(facts, lang, _needed(), mark=pre))
        if pre:
            body += "\n" + t(lang, "records_note")
        return _reply(s, body, [item("proceed", t(lang, "o_proceed")), item("edit", t(lang, "o_edit"))])  # Update 2: no Main menu
    if tok.startswith("RESULTS"):
        off = int(tok.split(":")[1]) if ":" in tok else 0
        return _results_page(db, s, off)
    if tok.startswith("DETAIL"):
        return _detail(db, s, int(tok.split(":")[1]))
    if tok.startswith("SHARE:"):
        return _share_scheme(db, s, int(tok.split(":")[1]))
    if tok == "WHY":
        return _why(db, s)
    if tok == "FEEDBACK_RATING":
        s.state = "FEEDBACK_RATING"
        opts = [item(i, "⭐" * i, f"{i} – {t(lang, f'r_{i}')}") for i in range(1, 6)]
        return _reply(s, t(lang, "q_rating"), opts + _nav(s, menu=False))
    if tok == "FEEDBACK_COMMENT":
        s.state = "FEEDBACK_COMMENT"
        return _reply(s, t(lang, "q_comment"), [item(0, t(lang, "o_skip"))] + _nav(s, menu=False), input_hint="text")
    if tok == "ENDED":
        s.state = "ENDED"
        return _reply(s, t(lang, "class_other"), [nav("change", lang, "o_edit"), nav("menu", lang, "o_menu")],
                      input_hint="text")
    return _advance(db, s)


def _advance(db: DB, s: ChatSession, prefix: str = "") -> BotReply:
    a = s.answers or {}
    if not a.get("_lang_done"):
        return _go(db, s, "LANG", prefix)
    if s.consent_status == "DECLINED":
        return _go(db, s, "DECLINED", prefix)
    if s.consent_status != "AGREED":
        return _go(db, s, "CONSENT", prefix)
    if s.prefilled and not a.get("_prefill_done"):
        pre = {k: v for k, v in s.prefilled.items() if k not in a}
        if "annual_family_income" in pre:
            pre.update({k: v for k, v in income_facts(pre["annual_family_income"]).items() if k != "annual_family_income"})
        _set_answers(s, _prefill_done=True, **pre)
        a = s.answers
    if a.get("class_passed") == "OTHER":            # not a student we can help: end right away, ask nothing more
        return _end_other(db, s)
    for key in _needed():
        if key not in a:
            return _go(db, s, f"ASK_{key}", prefix)
    if not a.get("_summary_ok"):
        return _go(db, s, "SUMMARY", prefix)
    r = _finish(db, s)
    if prefix:
        r.text = f"{prefix}\n\n{r.text}"
    return r


def _end_other(db: DB, s: ChatSession) -> BotReply:
    s.status = "COMPLETED"
    s.completed_at = s.completed_at or utcnow()
    s.eligible_count = 0
    db.query(Suggestion).filter(Suggestion.session_id == s.id).delete()
    _mark_referral(db, s, "COMPLETED")
    r = _go(db, s, "ENDED")
    r.events.append("completed")
    return r


def _mark_referral(db: DB, s: ChatSession, status: str):
    if s.referral_id:
        ref = db.get(Referral, s.referral_id)
        if ref:
            ref.status = status
            ref.updated_at = utcnow()


def _edit(db: DB, s: ChatSession) -> BotReply:
    """'Edit details': ask the questions again from the first one (language + consent kept)."""
    a = dict(s.answers or {})
    prev = {k: a[k] for k in FACT_KEYS if k in a}
    for k in FACT_KEYS + ["_summary_ok"]:
        a.pop(k, None)
    a["_prev"], a["_prefill_done"], a["_prefill_used"] = prev, True, False
    s.answers = a
    s.status = "ACTIVE" if s.status == "COMPLETED" else s.status
    return _go(db, s, f"ASK_{_needed()[0]}", t(s.language, "edit_restart"))


# ------------------------------------------------------------------ results, cards, detail
def _groups_label(groups, lang, rule=None) -> str:
    out = []
    for g in groups:
        if g == "income" and rule is not None and rule.Income_Max:
            out.append(t(lang, "grp_income", amt=inr(rule.Income_Max)))
        else:
            out.append(t(lang, f"grp_{g}"))
    return ", ".join(out)


def _tag(level: str, state_ut: str, lang: str) -> str:
    return t(lang, "central") if level == "Central" else state_ut


def _suggestions(db: DB, s: ChatSession) -> list[Suggestion]:
    return db.execute(select(Suggestion).where(Suggestion.session_id == s.id).order_by(Suggestion.rank)).scalars().all()


def _title_line(name: str, tag: str, dept: str) -> str:
    return " · ".join(x for x in (name, tag, dept) if x)


def _card(s: ChatSession, sug: Suggestion, profile) -> dict:
    lang = s.language
    rule = get_engine().by_id.get(sug.scheme_id)
    only = check_groups_open(profile, rule) if rule else []
    level = rule.Scheme_Level if rule else ""
    state_ut = rule.Scheme_State_UT if rule else ""
    tag = _tag(level, state_ut, lang) if rule else ""
    dept = (rule.Department or "").strip() if rule and not (rule.Department or "").lower().startswith("not specified") else ""
    see = t(lang, "see_site")
    label = _groups_label(only, lang, rule)
    return {"rank": sug.rank, "scheme_id": sug.scheme_id, "name": sug.scheme_name,
            "benefit": sug.benefit or "", "apply_url": sug.apply_url or "",
            "level": level, "state_ut": state_ut, "tag": tag, "department": dept,
            "title_line": _title_line(sug.scheme_name, tag, dept),
            "description": (rule.Short_Description if rule else "") or see,
            "eligibility": (rule.Short_Eligibility if rule else "") or see,
            "documents": (rule.Short_Documents if rule else "") or see,
            "url": (rule.Apply_URL if rule else sug.apply_url) or see,
            "labels": {"description": t(lang, "d_description"), "eligibility": t(lang, "d_eligibility"),
                       "documents": t(lang, "d_docs_short"), "url": t(lang, "d_apply")},
            "only_for": only, "only_for_label": label, "check": bool(only),
            "benefit_line": (rule.Short_Description if rule else "") or see,
            "check_note": (t(lang, "only_for", groups=label) + " – " + t(lang, "check_elig")) if only else "",
            "view_label": t(lang, "o_view")}


def _results_page(db: DB, s: ChatSession, start: int) -> BotReply:
    lang = s.language
    rows = _suggestions(db, s)
    total = len(rows)
    n = settings.max_results
    start = max(0, min(start, max(0, total - 1)))
    page = rows[start:start + n]
    for r in page:
        r.shown = True
    s.result_offset = start + len(page)
    s.state = "RESULTS"
    a = dict(s.answers or {})
    a["_view"] = f"RESULTS:{start}"
    s.answers = a
    profile = profile_from_facts(public_answers(s))
    cards = [_card(s, r, profile) for r in page]
    eng = get_engine()
    n_main = sum(1 for r in rows if r.scheme_id in eng.by_id and not check_groups_open(profile, eng.by_id[r.scheme_id]))
    extra = []
    if start + len(page) < total:
        extra.append("more")
    if s.feedback_rating is None and total:
        extra.append("rate")
    if not total:
        extra.append("change")
    if not page:
        text = t(lang, "results_none")
    elif n_main == 0:
        text = t(lang, "results_head_check_only", n=total, a=start + 1, b=start + len(page), total=total)
    else:
        text = t(lang, "results_head", n=len(page), a=start + 1, b=start + len(page), total=total)
    if page:
        text += "\n" + t(lang, "list_tap")
    opts = [item(c["rank"], f"{c['rank']}. {c['name']}", " · ".join(x for x in (c["tag"], c["department"]) if x))
            for c in cards]
    return BotReply(text=text, options=opts + _nav(s, *extra, menu=False), cards=cards, footer=t(lang, "results_foot") if page else "",
                    state=s.state, status=s.status, language=lang, input_hint="choice", view=f"RESULTS:{start}",
                    section_label=t(lang, "check_section") if any(c["check"] for c in cards) else "")


def _na(v, lang) -> str:
    return v if (v not in (None, "") and str(v).strip()) else t(lang, "na")


def detail_card(rule, lang: str, only_open: list | None = None) -> dict:
    d = scheme_detail(rule)
    only = d["only_for"] if only_open is None else only_open
    see = t(lang, "see_site")
    cat = d["category"]
    if cat and d["category_inferred"]:
        cat = f"{cat} ({t(lang, 'd_inferred')})"
    elif not cat:
        raw = (rule.Category_Raw or "").strip()
        cat = raw if raw and not raw.lower().startswith("not specified") else ""
    gender = d["gender"] or ((rule.Gender_Raw or "").strip() if rule.Gender_Raw and
                             not rule.Gender_Raw.lower().startswith("not specified") else "")
    income = t(lang, "d_income_upto", amt=inr(d["income_max"])) if d["income_max"] else d["income_raw"]
    tag = _tag(d["level"], d["state_ut"], lang)
    short = [("description", t(lang, "d_description"), d["short_description"] or see),
             ("eligibility", t(lang, "d_eligibility"), d["short_eligibility"] or see),
             ("documents", t(lang, "d_docs_short"), d["short_documents"] or see),
             ("url", t(lang, "d_apply"), rule.Apply_URL or see)]
    rows = [("type", t(lang, "d_type"), _na(d["type"], lang)),
            ("benefit", t(lang, "d_benefit"), _na(d["benefit"], lang)),
            ("stage", t(lang, "d_stage"), _na(d["stage"], lang)),
            ("category", t(lang, "d_category"), _na(cat, lang)),
            ("gender", t(lang, "d_gender"), _na(gender, lang)),
            ("income", t(lang, "d_income"), _na(income, lang))]
    if d["age"]:
        rows.append(("age", t(lang, "d_age"), d["age"]))
    rows.append(("domicile", t(lang, "d_domicile"), _na(d["domicile"], lang)))
    if only:
        rows.append(("only_for", t(lang, "d_only_for"), f"{_groups_label(only, lang, rule)} – {t(lang, 'check_elig')}"))
    rows += [("other", t(lang, "d_other"), _na(d["other"], lang)),
             ("deadline", t(lang, "d_deadline"), _na(d["deadline"], lang))]
    link = d["apply_url"]
    return {"scheme_id": d["scheme_id"], "title": d["name"], "tag": tag, "department": d["department"],
            "title_line": _title_line(d["name"], tag, d["department"]),
            "short": [{"key": k, "label": lb, "value": v, "na": v == see} for k, lb, v in short],
            "more_label": t(lang, "more_details"),
            "rows": [{"key": k, "label": lb, "value": v, "na": v == t(lang, "na")} for k, lb, v in rows],
            "apply_url": link, "apply_url_verified": d["apply_url_verified"],
            "link_label": t(lang, "d_link"), "link_note": "" if (not link or d["apply_url_verified"]) else t(lang, "link_unverified"),
            "note": t(lang, "guidance")}


ICONS = {"type": "📂", "benefit": "💰", "stage": "🎓", "category": "👥", "gender": "🚻", "income": "💵", "age": "🎂",
         "domicile": "📍", "only_for": "⚠️", "other": "📋", "documents": "📄", "deadline": "⏰",
         "description": "📝", "eligibility": "✅", "url": "🔗"}


def detail_text(card: dict, lang: str) -> str:
    lines = [f"*{card['title']}*" + "".join(f" · {x}" for x in (card["tag"], card.get("department")) if x)]
    for r in card.get("short", []):
        lines.append(f"{ICONS.get(r['key'], '•')} *{r['label']}:* {r['value']}")
    lines.append("")
    lines.append(f"*{card.get('more_label', '')}*")
    for r in card["rows"]:
        lines.append(f"{ICONS.get(r['key'], '•')} {r['label']}: {r['value']}")
    if card["link_note"]:
        lines.append(f"🔗 {card['link_note']}")
    lines.append("")
    lines.append(card["note"])
    return "\n".join(lines)


def _rule_for_rank(db: DB, s: ChatSession, rank: int):
    sug = next((r for r in _suggestions(db, s) if r.rank == rank), None)
    return sug, (get_engine().by_id.get(sug.scheme_id) if sug else None)


def _detail(db: DB, s: ChatSession, rank: int) -> BotReply:
    lang = s.language
    sug, rule = _rule_for_rank(db, s, rank)
    if sug is None or rule is None:
        return _results_page(db, s, 0)
    s.state = "DETAIL"
    profile = profile_from_facts(public_answers(s))
    card = detail_card(rule, lang, check_groups_open(profile, rule))
    # Update 2: exactly 3 CTAs (no Main menu button; typing MENU still works, WhatsApp adds a hint)
    opts = [nav("back", lang, "o_back"), nav("share", lang, "o_share_scheme"), nav("rate", lang, "o_feedback")]
    return BotReply(text=detail_text(card, lang), options=opts, detail=card, state=s.state, status=s.status,
                    language=lang, view=f"DETAIL:{rank}")


def _share_scheme(db: DB, s: ChatSession, rank: int) -> BotReply:
    """Pre-formatted message the student can forward; carries their peer-referral (REF) links."""
    from urllib.parse import quote
    lang = s.language
    sug, rule = _rule_for_rank(db, s, rank)
    if sug is None or rule is None:
        return _results_page(db, s, 0)
    s.state = "SHARE"
    links = A.share_links(db, s)
    msg = t(lang, "share_scheme_msg", name=rule.Scheme_Name, tag=_tag(rule.Scheme_Level, rule.Scheme_State_UT, lang),
            desc=rule.Short_Description or t(lang, "see_site"), url=rule.Apply_URL or t(lang, "see_site"),
            wa=links["whatsapp_link"] or links["web_link"], web=links["web_link"])
    share = dict(links, message=msg, subject=t(lang, "share_subject"),
                 whatsapp_share_url="https://wa.me/?text=" + quote(msg),
                 email_url="mailto:?subject=" + quote(t(lang, "share_subject")) + "&body=" + quote(msg),
                 labels={"whatsapp": t(lang, "sh_whatsapp"), "email": t(lang, "sh_email"), "copy": t(lang, "sh_copy"),
                         "more": t(lang, "sh_more"), "copied": t(lang, "sh_copied")}, scheme_id=rule.Scheme_ID)
    opts = [nav("back", lang, "o_back"), nav("rate", lang, "o_feedback")]
    return BotReply(text=t(lang, "share_scheme_intro") + "\n\n" + msg, options=opts, state=s.state, status=s.status,
                    language=lang, view=f"SHARE:{rank}", share=share, events=["share_scheme"])


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
    _mark_referral(db, s, "COMPLETED")
    summary = t(lang, "summary", facts=facts_inline(facts, lang))
    reply = _go(db, s, "RESULTS:0")
    reply.text = f"{summary}\n\n{reply.text}"
    reply.status = "COMPLETED"
    reply.events.append("completed")
    return reply


# ------------------------------------------------------------------ why / fallback
def _why(db: DB, s: ChatSession) -> BotReply:
    lang = s.language
    s.state = "WHY"
    a = s.answers or {}
    said = a.get("_why_cat")
    cur = a.get("category")
    facts = public_answers(s)
    done = _done(s) and a.get("_summary_ok")
    text = t(lang, "why", facts=facts_block(facts, lang, _needed())) if done else t(lang, "why_early")
    opts = [nav("change", lang, "o_edit")]
    if said and cur and said != cur:
        text += "\n\n" + t(lang, "why_cat_diff", said=t(lang, f"cat_{said}"), cat=t(lang, f"cat_{cur}"))
        opts.insert(0, {"id": f"setcat:{said}", "label": "✔ " + t(lang, f"cat_{said}"), "kind": "nav"})
    elif cur and done:
        text += "\n\n" + t(lang, "why_cat_same", cat=t(lang, f"cat_{cur}"))
    if done:
        opts.append(nav("list", lang, "o_back_list"))
    elif a.get("_hist"):
        opts.append(nav("back", lang, "o_back"))
    if not done:                                   # Update 2: no Main menu button after the results
        opts.append(nav("menu", lang, "o_menu"))
    return BotReply(text=text, options=opts[:4] if len(opts) > 4 else opts, state=s.state, status=s.status,
                    language=lang, view="WHY")


def _fallback(db: DB, s: ChatSession, text: str) -> BotReply:
    """Unknown input: explain 'why' questions, otherwise a friendly hint + the current options again."""
    said, any_cat = mentioned_category(text)
    view = _cur_view(s)
    if s.consent_status == "AGREED" and (WHY_RX.search(text or "") or (any_cat and not view.startswith("ASK_category"))):
        _set_answers(s, _why_cat=said)
        return _go(db, s, "WHY")
    return _go(db, s, view or "MENU", t(s.language, "fallback"), push=False)


def restart(db: DB, s: ChatSession) -> tuple[ChatSession, BotReply]:
    if s.status in ("ACTIVE",):
        s.status = "RESTARTED"
    ref = db.get(Referral, s.referral_id) if s.referral_id else None
    return start_session(db, channel=s.channel, wa_id=s.wa_id, referral=ref, source_system=s.source_system,
                         token_hash=s.token_hash, inherit_from=s, language=chosen_language(s), greet_lang=s.language)


def _resolve(s: ChatSession, text: str) -> str:
    """Map a typed button label (any language), or the number of a non-numeric option, back to its id."""
    low = _clean(text)
    opts = (s.last_reply or {}).get("options") or []
    for o in opts:
        if low == _clean(str(o.get("label", ""))) and o.get("id") not in (None, ""):
            return str(o["id"])
    items = [o for o in opts if o.get("kind", "item") == "item"]
    if low.isdigit() and items and not any(str(o.get("id")).isdigit() for o in items) and 1 <= int(low) <= len(items):
        return str(items[int(low) - 1]["id"])
    # detail / share screens only have buttons: "1", "2", "3" = first, second, third button
    buttons = [o for o in opts if not o.get("optional")]
    if low.isdigit() and not items and str(_cur_view(s) or "").startswith(("DETAIL", "SHARE")) \
            and 1 <= int(low) <= len(buttons):
        return str(buttons[int(low) - 1]["id"])
    return text


def _set_language(s: ChatSession, low: str) -> bool:
    for i, code in enumerate(LANG_ORDER, start=1):
        names = {str(i), code, LANGS[code]["en"].lower(), LANGS[code]["native"].lower(), lang_label(code).lower()}
        if low in names:
            s.language = code
            return True
    return False


YES = {"yes", "y", "haan", "han", "ha", "हाँ", "हां", "ok", "okay", "agree", "i agree"}
NO = {"no", "n", "nahi", "nahin", "नहीं", "disagree", "don't agree", "dont agree"}


def _set_consent(db: DB, s: ChatSession, agreed: bool):
    s.consent_status = "AGREED" if agreed else "DECLINED"
    s.consent_at = utcnow()
    s.consent_version = CONSENT_VERSION
    if not agreed:                              # keep nothing personal beyond the decision itself
        a = {k: v for k, v in (s.answers or {}).items() if k in ("_lang_done", "_view", "_hist")}
        s.answers = a
        s.prefilled = {}
        s.status = "CONSENT_DECLINED"
        _mark_referral(db, s, "CONSENT_DECLINED")
    elif s.status == "CONSENT_DECLINED":
        s.status = "ACTIVE"
        _mark_referral(db, s, "IN_CONVERSATION")


def handle_message(db: DB, s: ChatSession, text: str) -> tuple[ChatSession, BotReply]:
    """Process one user input for session s. May return a NEW session (after hi/restart)."""
    text = _resolve(s, text)
    low = _clean(text)
    lang = s.language
    s.updated_at = utcnow()
    view = _cur_view(s) or s.state

    if low in GREET | RESTART:
        return restart(db, s)
    if low in STOP:
        s.status = "OPTED_OUT"
        s.state = "ENDED"
        _mark_referral(db, s, "OPTED_OUT")
        return s, BotReply(text=t(lang, "stopped"), state=s.state, status=s.status, language=lang,
                           input_hint="text", events=["opted_out"])
    if s.status == "OPTED_OUT":
        return s, BotReply(text="", state=s.state, status=s.status, language=lang, silent=True)

    # ---- language first, then consent
    if view == "LANG" or s.state == "LANG":
        if not _set_language(s, low):
            if low in BACK and (s.answers or {}).get("_hist"):
                return s, _back(db, s)
            if low in MENU and (s.answers or {}).get("_lang_done"):
                return s, _go(db, s, "MENU")
            return s, _go(db, s, "LANG", t(lang, "fallback"), push=False)
        first_time = not (s.answers or {}).get("_lang_done")
        _set_answers(s, _lang_done=True)
        if first_time or not (s.answers or {}).get("_hist"):
            return s, _advance(db, s)
        r = _back(db, s)                     # return to where the user was, now in the new language
        r.text = t(s.language, "lang_set", language=lang_label(s.language)) + "\n\n" + r.text
        return s, r
    if low in LANGW:
        return s, _go(db, s, "LANG")
    if s.consent_status != "AGREED":
        if low in {"agree"} | YES and view in ("CONSENT", "DECLINED"):
            _set_consent(db, s, True)
            return s, _advance(db, s)
        if low in {"disagree"} | NO and view == "CONSENT":
            _set_consent(db, s, False)
            return s, _go(db, s, "DECLINED")
        if low in BACK and view == "CONSENT":
            return s, _back(db, s)
        if low in HELP:
            return s, _go(db, s, view or "CONSENT", t(lang, "help"), push=False)
        return s, _go(db, s, "DECLINED" if s.consent_status == "DECLINED" else "CONSENT",
                      "" if view in ("CONSENT", "DECLINED") and low in MENU else t(lang, "fallback"), push=False)

    # ---- global navigation
    a = s.answers or {}
    done = _done(s) and bool(a.get("_summary_ok"))
    if low in HELP:
        return s, _go(db, s, view or "MENU", t(lang, "help"), push=False)
    if low in BACK:
        return s, _back(db, s)
    if low in MENU:
        return s, _go(db, s, "MENU")
    if low in CHANGE:
        return s, _edit(db, s)
    if low == "find":
        if a.get("class_passed") == "OTHER" and all(k in a for k in _needed()):
            return s, _go(db, s, "ENDED")
        return s, (_go(db, s, "RESULTS:0") if done else _advance(db, s))
    if low in {"rate", "feedback", "share feedback"} and done:
        return s, _go(db, s, "FEEDBACK_RATING")
    if low in {"share", "share scheme"} and view.startswith(("DETAIL", "SHARE")) and done:
        return s, _go(db, s, "SHARE:" + view.split(":")[1])
    if low == "list" and done:
        n = settings.max_results
        return s, _go(db, s, f"RESULTS:{max(0, (s.result_offset or n) - n)}")
    if low in MORE and view.startswith(("RESULTS", "DETAIL")) and done:
        total = len(_suggestions(db, s))
        if (s.result_offset or 0) >= total:
            return s, _go(db, s, view, t(lang, "no_more"), push=False)
        return s, _go(db, s, f"RESULTS:{s.result_offset}")
    if low.startswith("setcat:"):
        cat = F.norm_category(text.split(":", 1)[1])
        if cat:
            _set_answers(s, category=cat, _summary_ok=False)
            return s, _advance(db, s, t(lang, "updated", f=t(lang, "f_category"), v=t(lang, f"cat_{cat}")))

    # ---- view-specific input
    if view == "SUMMARY":
        if low in {"proceed", "1"} | YES:
            pre = s.prefilled or {}
            _set_answers(s, _summary_ok=True,
                         _prefill_used=bool(pre) and all(a.get(k) == v for k, v in pre.items() if k in _needed()))
            return s, _advance(db, s)
        if low in {"edit", "2", "edit details"}:
            return s, _edit(db, s)
        return s, _fallback(db, s, text)

    if view.startswith("ASK_"):
        key = view[4:]
        v = parse_answer(key, text, lang)
        if v is MISSING:
            return s, _fallback(db, s, text)
        kv = income_facts(v) if key == "annual_family_income" else {key: v}
        _set_answers(s, _summary_ok=False, **kv)
        return s, _advance(db, s)

    if view in ("MENU", "ENDED", "SHARED") or view.startswith("SHARE:"):
        return s, _fallback(db, s, text)

    if view.startswith(("RESULTS", "DETAIL", "WHY")):
        if low.isdigit() and done and any(r.rank == int(low) for r in _suggestions(db, s)):
            return s, _go(db, s, f"DETAIL:{int(low)}")
        return s, _fallback(db, s, text)

    if view == "FEEDBACK_RATING":
        stars = low.replace(" ", "")
        rating = int(low[0]) if low[:1] in "12345" and low[:1] else (len(stars) if stars and set(stars) == {"⭐"} and len(stars) <= 5 else 0)
        if rating:
            s.feedback_rating = rating
            return s, _go(db, s, "FEEDBACK_COMMENT")
        return s, _go(db, s, view, t(lang, "fallback"), push=False)

    if view == "FEEDBACK_COMMENT":
        if low not in SKIP | {"0"}:
            s.feedback_comment = text.strip()[:500]
        links = A.share_links(db, s)
        share = t(lang, "share", wa=links["whatsapp_link"] or t(lang, "share_no_wa"), web=links["web_link"],
                  code=links["share_code"])
        _set_answers(s, _view="SHARED")
        s.state = "SHARED"
        opts = [nav("list", lang, "o_back_list")]
        return s, BotReply(text=share, options=opts, state=s.state, status=s.status, language=lang,
                           events=["feedback"], share=links, view="SHARED")

    return s, _advance(db, s)


# ------------------------------------------------------------------ plain-text rendering (WhatsApp fallback, SMS, logs)
def render_cards(r: BotReply) -> str:
    lang = r.language
    parts, check_hdr = [], False
    for c in r.cards:
        if c.get("check") and not check_hdr:
            parts.append("— " + t(lang, "check_section") + " —")
            check_hdr = True
        # Update 2: compact listing - number + name · State/Central · Department (details only on "View details")
        lines = [f"*{c['rank']}. {c.get('title_line') or c['name']}*"]
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def render_text(r: BotReply, limit: int = 4000, with_options: bool = True) -> str:
    lang = r.language
    parts = [r.text, render_cards(r)]
    if r.footer:
        parts.append(r.footer)
    if with_options and r.options:
        items = [o for o in r.options if o.get("kind", "item") == "item"]
        navs = [o for o in r.options if o.get("kind") == "nav"]
        if items:
            numeric = all(str(o["id"]).isdigit() for o in items)
            parts.append(t(lang, "reply_number") + "\n" + "\n".join(
                f"{o['id'] if numeric else i}. {o['label']}" + (f" ({o['desc']})" if o.get("desc") and not numeric else "")
                for i, o in enumerate(items, start=1)))
        if navs:
            parts.append("\n".join(f"▫️ {o['label']} → {o['id'].upper()}" for o in navs))
    out = "\n\n".join(p for p in parts if p)
    return out if len(out) <= limit else out[: limit - 1] + "…"
