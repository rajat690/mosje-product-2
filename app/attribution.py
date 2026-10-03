"""Entry-source attribution for every session (WhatsApp and web).

Taxonomy (ChatSession.entry_source):
    OUTREACH       user clicked a link from a registered outreach message (code OM-xxxxxx, optional
                   per-recipient code Rxxxxxxxx), or opened /companion?src=outreach&om=...
    PEER_REFERRAL  user came via another user's share link/code (REF-xxxxxx)
    ORGANIC        no code / params: user found the bot on their own (channel tells web vs whatsapp)
First-touch details (raw text or URL params, utm_*, resolved ids, timestamp) go to ChatSession.first_touch.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote, urlencode

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .config import settings
from .db import KV, ChatSession, OutreachMessage, OutreachRecipient, Referral, utcnow

OUTREACH, ORGANIC, PEER = "OUTREACH", "ORGANIC", "PEER_REFERRAL"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"        # no 0/O, 1/I/L confusion

OM_RE = re.compile(r"\b(OM-[A-Z0-9]{4,12})(?:-(R[A-Z0-9]{4,14}))?\b", re.I)
REF_RE = re.compile(r"\b(REF-[A-Z0-9]{4,12})\b", re.I)
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


def new_code(prefix: str, n: int = 6) -> str:
    return prefix + "".join(secrets.choice(ALPHABET) for _ in range(n))


def unique_code(db: DB, model, prefix: str, n: int = 6, col: str = "code") -> str:
    for _ in range(20):
        c = new_code(prefix, n)
        if not db.execute(select(model).where(getattr(model, col) == c)).first():
            return c
    raise RuntimeError("could not allocate a unique code")


@dataclass
class Attribution:
    entry_source: str = ORGANIC
    outreach: Optional[OutreachMessage] = None
    recipient: Optional[OutreachRecipient] = None
    referral: Optional[Referral] = None          # referral to link / pre-fill from (via recipient code)
    referrer: Optional[ChatSession] = None
    first_touch: dict = field(default_factory=dict)

    @property
    def has_code(self) -> bool:
        return self.entry_source != ORGANIC


def _find_outreach(db: DB, om: str, source_system: Optional[str] = None) -> Optional[OutreachMessage]:
    if not om:
        return None
    o = db.execute(select(OutreachMessage).where(OutreachMessage.code == om.upper())).scalar_one_or_none()
    if o:
        return o
    q = select(OutreachMessage).where(OutreachMessage.message_id == om)
    if source_system:
        q = q.where(OutreachMessage.source_system == source_system)
    rows = db.execute(q).scalars().all()
    return rows[0] if len(rows) == 1 else None      # message_id is only unique per source_system


def _find_recipient(db: DB, o: Optional[OutreachMessage], r: str) -> Optional[OutreachRecipient]:
    if not r:
        return None
    rec = db.execute(select(OutreachRecipient).where(OutreachRecipient.code == r.upper())).scalar_one_or_none()
    if rec and (o is None or rec.outreach_id == o.id):
        return rec
    if o is not None:        # a Product 1 may also put its own recipient ref (e.g. external_ref) in r=
        return db.execute(select(OutreachRecipient).where(OutreachRecipient.outreach_id == o.id,
                                                          OutreachRecipient.recipient_ref == r)).scalar_one_or_none()
    return None


def _referral_for(db: DB, o: Optional[OutreachMessage], rec: Optional[OutreachRecipient], r: str) -> Optional[Referral]:
    if rec and rec.referral_id:
        return db.get(Referral, rec.referral_id)
    ref_value = rec.recipient_ref if rec else r
    if o and ref_value:
        return db.execute(select(Referral).where(Referral.source_system == o.source_system,
                                                 Referral.external_ref == ref_value)).scalar_one_or_none()
    return None


def _find_referrer(db: DB, code: str) -> Optional[ChatSession]:
    return db.execute(select(ChatSession).where(ChatSession.share_code == code.upper())).scalar_one_or_none()


def from_whatsapp_text(db: DB, text: str) -> Attribution:
    """Parse a first inbound WhatsApp message (e.g. the pre-filled wa.me text) for OM-/REF- codes."""
    now = utcnow().isoformat() + "Z"
    m = OM_RE.search(text or "")
    if m:
        o = _find_outreach(db, m.group(1))
        rec = _find_recipient(db, o, m.group(2) or "")
        return Attribution(OUTREACH, o, rec, _referral_for(db, o, rec, ""), None,
                           {"channel": "whatsapp", "raw_text": (text or "")[:300], "om_code": m.group(1).upper(),
                            "recipient_code": (m.group(2) or "").upper() or None,
                            "resolved": bool(o), "at": now})
    m = REF_RE.search(text or "")
    if m:
        ref = _find_referrer(db, m.group(1))
        return Attribution(PEER, referrer=ref,
                           first_touch={"channel": "whatsapp", "raw_text": (text or "")[:300],
                                        "share_code": m.group(1).upper(), "resolved": bool(ref), "at": now})
    return Attribution(ORGANIC, first_touch={"channel": "whatsapp", "raw_text": (text or "")[:300], "at": now})


def from_web_params(db: DB, params: dict | None) -> Attribution:
    """Resolve /companion URL parameters: src, om, r, ref, utm_*."""
    p = {str(k): str(v)[:200] for k, v in (params or {}).items() if v not in (None, "")}
    now = utcnow().isoformat() + "Z"
    ft = {"channel": "web", "params": p, "at": now}
    utm = {k: p[k] for k in UTM_KEYS if k in p}
    src = p.get("src", "").lower()
    om = p.get("om") or ""
    if not om and src in ("", "outreach") and utm.get("utm_campaign"):
        om = utm["utm_campaign"] if _find_outreach(db, utm["utm_campaign"]) else ""
    if src == "outreach" or (om and src != "referral"):
        o = _find_outreach(db, om)
        rec = _find_recipient(db, o, p.get("r", ""))
        ft.update({"om": om or None, "recipient": p.get("r"), "resolved": bool(o)})
        return Attribution(OUTREACH, o, rec, _referral_for(db, o, rec, p.get("r", "")), None, ft)
    if src == "referral" or p.get("ref"):
        code = p.get("ref", "")
        ref = _find_referrer(db, code) if code else None
        ft.update({"share_code": code.upper() or None, "resolved": bool(ref)})
        return Attribution(PEER, referrer=ref, first_touch=ft)
    return Attribution(ORGANIC, first_touch=ft)


def apply(s: ChatSession, a: Attribution) -> None:
    s.entry_source = a.entry_source
    s.first_touch = a.first_touch
    s.outreach_id = a.outreach.id if a.outreach else None
    s.outreach_recipient_id = a.recipient.id if a.recipient else None
    s.referrer_session_id = a.referrer.id if a.referrer else None
    if a.outreach and not s.source_system:
        s.source_system = a.outreach.source_system


def inherit(new: ChatSession, old: ChatSession) -> None:
    """A restart keeps the original first-touch attribution of the user journey."""
    new.entry_source = old.entry_source
    new.first_touch = dict(old.first_touch or {}, inherited_from=old.public_id)
    new.outreach_id = old.outreach_id
    new.outreach_recipient_id = old.outreach_recipient_id
    new.referrer_session_id = old.referrer_session_id


# ------------------------------------------------------------------ links
def wa_number(db: DB | None = None) -> str:
    if settings.wa_display_number:
        return settings.wa_display_number
    if db is not None:
        kv = db.get(KV, "wa_display_number")
        if kv and kv.value:
            return kv.value
    return ""


def remember_wa_number(db: DB, number: str) -> None:
    digits = "".join(ch for ch in (number or "") if ch.isdigit())
    if not digits or settings.wa_display_number:
        return
    kv = db.get(KV, "wa_display_number")
    if kv is None:
        db.add(KV(key="wa_display_number", value=digits))
    elif kv.value != digits:
        kv.value = digits


def wa_link(db: DB, text: str) -> Optional[str]:
    n = wa_number(db)
    return f"https://wa.me/{n}?text={quote(text)}" if n else None


def web_link(params: dict) -> str:
    return f"{settings.public_base_url}/companion?{urlencode(params)}"


def outreach_wa_text(o: OutreachMessage, rec: Optional[OutreachRecipient] = None) -> str:
    code = o.code + (f"-{rec.code}" if rec else "")
    return f"Hi, I want to find scholarships. Code {code}"


def outreach_links(db: DB, o: OutreachMessage, rec: Optional[OutreachRecipient] = None) -> dict:
    web = {"src": "outreach", "om": o.code}
    if rec:
        web["r"] = rec.code
    web.update({"utm_source": o.source_system, "utm_medium": o.channel, "utm_campaign": o.code})
    text = outreach_wa_text(o, rec)
    return {"whatsapp_text": text, "whatsapp_link": wa_link(db, text), "web_link": web_link(web)}


def ensure_share_code(db: DB, s: ChatSession) -> str:
    if not s.share_code:
        s.share_code = unique_code(db, ChatSession, "REF-", 6, col="share_code")
    return s.share_code


def share_links(db: DB, s: ChatSession | None, code: str | None = None, lang: str | None = None) -> dict:
    """Personal refer-a-friend links. `code` overrides the session's own code (a saved student keeps one code).
    The ready-to-forward message is in the student's language (`lang`, else the session's language)."""
    from .conversation.texts import t as _t
    code = code or ensure_share_code(db, s)
    text = f"Hi, my friend suggested this scholarship helper. Code {code}"
    web = web_link({"src": "referral", "ref": code})
    wa = wa_link(db, text)
    # Update 3 'Refer a friend': a ready-to-forward message for the WhatsApp share intent (wa.me/?text=...)
    msg = _t(lang or (s.language if s is not None else None) or "en", "share_invite", link=wa or web) + (f"\n🌐 {web}" if wa else "")
    return {"share_code": code, "whatsapp_link": wa, "whatsapp_text": text, "web_link": web,
            "share_message": msg, "whatsapp_share_url": "https://wa.me/?text=" + quote(msg)}


def peer_referral_count(db: DB, s: ChatSession) -> int:
    """New user journeys started with this session's share code (restarts are not double counted)."""
    rows = db.execute(select(ChatSession.first_touch).where(ChatSession.referrer_session_id == s.id)).scalars().all()
    return sum(1 for ft in rows if not (ft or {}).get("inherited_from"))
