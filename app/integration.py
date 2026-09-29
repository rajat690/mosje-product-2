"""Integration contract v1 for Product 1 systems (all endpoints need X-API-Key).

See INTEGRATION_SPEC.md for the human-readable contract.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from . import attribution as A
from . import facts as F
from .conversation.texts import LANG_CODES
from . import results
from .channels import whatsapp
from .config import settings
from .db import ChatSession, OutreachMessage, OutreachRecipient, Referral, SourceSystem, get_db, utcnow
from .eligibility import get_engine
from .security import SOURCE_RE, Caller, require_api_key

router = APIRouter(prefix="/v1", tags=["integration v1"])

MAX_BATCH = 5000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
REASONS = {"PROBABLE", "UNLINKED", "MATCHED", "NO_SCHEMES", "OTHER"}
FIELDS = ["external_ref", "source_system", "mobile", "name", "state", "class_passed", "category", "gender",
          "annual_family_income", "disability", "dob", "reason", "language"]


def _err(status: int, code: str, msg: str):
    raise HTTPException(status, detail={"error": code, "message": msg})


def ensure_source(db: DB, name: str) -> SourceSystem:
    src = db.execute(select(SourceSystem).where(SourceSystem.name == name)).scalar_one_or_none()
    if not src:
        src = SourceSystem(name=name)
        db.add(src)
        db.flush()
    return src


# ------------------------------------------------------------------ referral ingestion
def validate_item(raw: dict, default_source: Optional[str], caller: Caller) -> tuple[Optional[dict], list[str], list[str]]:
    errors, warns = [], []
    raw = {str(k).strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in (raw or {}).items()}
    ext = str(raw.get("external_ref") or "").strip()
    if not ext:
        errors.append("external_ref is required")
    elif len(ext) > 100:
        errors.append("external_ref longer than 100 characters")
    try:
        source = caller.resolve_source(raw.get("source_system") or default_source, required=True)
    except HTTPException as e:
        errors.append(e.detail["message"] if isinstance(e.detail, dict) else str(e.detail))
        source = None
    mobile = None
    if raw.get("mobile") not in (None, ""):
        mobile = F.norm_mobile(raw.get("mobile"))
        if not mobile:
            errors.append(f"mobile '{raw.get('mobile')}' is not a valid number (10-digit Indian or with country code)")
    else:
        warns.append("mobile missing: WhatsApp cannot recognise this student (web chat still works)")
    reason = str(raw.get("reason") or "").strip().upper() or None
    if reason and reason not in REASONS:
        warns.append(f"reason '{reason}' is not a standard value ({', '.join(sorted(REASONS))}); stored as given")
    lang = str(raw.get("language") or "").strip().lower() or None
    if lang and lang not in LANG_CODES:
        warns.append(f"language '{lang}' not supported ({', '.join(LANG_CODES)}); ignored")
        lang = None
    facts, fw = F.normalise_facts(raw)
    warns += fw
    if errors:
        return None, errors, warns
    name = str(raw.get("name") or "").strip()[:200] or None
    return {"external_ref": ext, "source_system": source, "mobile": mobile, "name": name,
            "first_name": F.first_name(name), "facts": facts, "reason": reason[:50] if reason else None,
            "language": lang}, [], warns


def upsert_items(db: DB, items: list[dict], default_source: Optional[str], caller: Caller) -> dict:
    if len(items) > MAX_BATCH:
        _err(413, "batch_too_large", f"Max {MAX_BATCH} referrals per request; split the batch.")
    created = updated = 0
    rejected, warnings = [], []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            rejected.append({"index": i, "external_ref": None, "errors": ["item must be a JSON object"]})
            continue
        v, errs, warns = validate_item(raw, default_source, caller)
        if errs:
            rejected.append({"index": i, "external_ref": (raw or {}).get("external_ref"), "errors": errs})
            continue
        if warns:
            warnings.append({"index": i, "external_ref": v["external_ref"], "warnings": warns})
        ensure_source(db, v["source_system"])
        r = db.execute(select(Referral).where(Referral.source_system == v["source_system"],
                                              Referral.external_ref == v["external_ref"])).scalar_one_or_none()
        if r is None:
            r = Referral(source_system=v["source_system"], external_ref=v["external_ref"], status="RECEIVED")
            db.add(r)
            created += 1
        else:
            updated += 1
        for k in ("mobile", "name", "first_name", "reason", "language"):
            if v[k] is not None:
                setattr(r, k, v[k])
        merged = dict(r.facts or {})
        merged.update(v["facts"])
        r.facts = merged
        r.updated_at = utcnow()
        db.flush()
    db.commit()
    return {"received": len(items), "created": created, "updated": updated,
            "rejected_count": len(rejected), "rejected": rejected, "warnings": warnings}


class ReferralIn(BaseModel):
    external_ref: str = Field(..., examples=["P1-STU-000123"])
    source_system: Optional[str] = Field(None, examples=["p1-rajat"])
    mobile: Optional[str] = Field(None, examples=["9876543210"])
    name: Optional[str] = Field(None, examples=["Aarav Sharma"])
    state: Optional[str] = Field(None, examples=["Rajasthan"])
    class_passed: Optional[str] = Field(None, examples=["X"])
    category: Optional[str] = Field(None, examples=["SC"])
    gender: Optional[str] = Field(None, examples=["Male"])
    annual_family_income: Optional[Any] = Field(None, examples=[180000])
    disability: Optional[Any] = Field(None, examples=[False])
    dob: Optional[str] = Field(None, examples=["2010-07-15"])
    reason: Optional[str] = Field(None, examples=["PROBABLE"])
    language: Optional[str] = Field(None, examples=["hi"])

    model_config = {"extra": "allow"}


class ReferralBatch(BaseModel):
    source_system: Optional[str] = Field(None, description="Default for items without source_system")
    referrals: list[dict] = Field(..., description="List of ReferralIn objects",
                                  json_schema_extra={"items": ReferralIn.model_json_schema()})


@router.post("/referrals")
def post_referrals(body: ReferralBatch, db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    return upsert_items(db, body.referrals, body.source_system, caller)


def _read_upload(name: str, data: bytes) -> list[dict]:
    name = (name or "").lower()
    if name.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header = [str(h or "").strip().lower() for h in next(rows, [])]
        out = []
        for r in rows:
            if r is None or all(v in (None, "") for v in r):
                continue
            d = {}
            for h, v in zip(header, r):
                if not h:
                    continue
                if isinstance(v, float) and v.is_integer():
                    v = int(v)
                d[h] = v.isoformat()[:10] if hasattr(v, "isoformat") else ("" if v is None else str(v))
            out.append(d)
        wb.close()
        return out
    if name.endswith(".csv") or name.endswith(".txt"):
        text = data.decode("utf-8-sig", errors="replace")
        return [dict(r) for r in csv.DictReader(io.StringIO(text)) if any((v or "").strip() for v in r.values())]
    _err(415, "unsupported_file_type", "Upload a .csv or .xlsx file (see templates/referrals_template.csv).")


@router.post("/referrals/upload")
async def upload_referrals(file: UploadFile = File(...), source_system: Optional[str] = Form(None),
                           db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        _err(413, "file_too_large", "Max 5 MB per upload.")
    items = _read_upload(file.filename, data)
    out = upsert_items(db, items, source_system, caller)
    out["file"] = file.filename
    return out


def _get_referral(db: DB, caller: Caller, external_ref: str, source_system: Optional[str]) -> Referral:
    source = caller.resolve_source(source_system, required=True)
    r = db.execute(select(Referral).where(Referral.source_system == source,
                                          Referral.external_ref == external_ref)).scalar_one_or_none()
    if not r:
        _err(404, "referral_not_found", f"No referral '{external_ref}' for source_system '{source}'.")
    return r


@router.get("/referrals/{external_ref}")
def get_referral(external_ref: str, source_system: Optional[str] = None, db: DB = Depends(get_db),
                 caller: Caller = Depends(require_api_key)):
    return results.referral_view(db, _get_referral(db, caller, external_ref, source_system))


class InviteIn(BaseModel):
    template: Optional[str] = Field(None, description="Approved WhatsApp template name (default WHATSAPP_INVITE_TEMPLATE)")
    language: Optional[str] = Field(None, description="Template language code, e.g. en_US, en, hi")
    params: Optional[list[str]] = Field(None, description="Body parameters; default [first_name, class] for custom templates")


@router.post("/referrals/{external_ref}/invite")
def invite_referral(external_ref: str, body: InviteIn | None = None, source_system: Optional[str] = None,
                    db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    body = body or InviteIn()
    r = _get_referral(db, caller, external_ref, source_system)
    if not r.mobile:
        _err(422, "no_mobile", "This referral has no mobile number.")
    if r.status == "OPTED_OUT":
        _err(409, "opted_out", "The student replied STOP; do not message them.")
    name = body.template or settings.invite_template
    lang = body.language or settings.invite_template_lang
    params = body.params
    if params is None and name != "hello_world":
        params = [r.first_name or "Student", (r.facts or {}).get("class_passed", "X")]
    status, mid = whatsapp.send_template(r.mobile, name, lang, params)
    r.invite_status = f"{status} ({name}) at {results.iso(utcnow())}"[:200]
    if status == "accepted" and r.status == "RECEIVED":
        r.status = "INVITED"
    r.updated_at = utcnow()
    from .conversation.core import log_message
    log_message(db, None, "out", f"[template {name}] referral {r.external_ref}", channel="whatsapp",
                external_id=mid, status=status)
    db.commit()
    return {"external_ref": r.external_ref, "status": r.status, "invite_status": r.invite_status, "message_id": mid}


# ------------------------------------------------------------------ outreach message registry + trackable links
class OutreachIn(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=100, examples=["2026-10-01-probable-wave1"])
    source_system: Optional[str] = Field(None, description="Only needed with the admin key")
    campaign: Optional[str] = Field(None, max_length=200, examples=["PROBABLE discovery – Rajasthan – wave 1"])
    channel: str = Field("whatsapp", pattern="^(whatsapp|sms|email)$")
    template_text: Optional[str] = Field(None, max_length=4000)
    template_version: Optional[str] = Field(None, max_length=50, examples=["scholarship_discovery_invite_en v1"])
    sent_at: Optional[str] = Field(None, description="ISO-8601, e.g. 2026-10-01T09:30:00+05:30")
    recipients: Optional[list[str]] = Field(None, description="Optional recipient refs (usually referral external_ref) "
                                                              "for per-recipient links; max 5000")


class RecipientsIn(BaseModel):
    recipients: list[str] = Field(..., min_length=1)


def _add_recipients(db: DB, o: OutreachMessage, refs: list[str]) -> list[OutreachRecipient]:
    if len(refs) > MAX_BATCH:
        _err(413, "batch_too_large", f"Max {MAX_BATCH} recipients per request.")
    out = []
    for ref in refs:
        ref = str(ref or "").strip()[:100]
        if not ref:
            continue
        rec = db.execute(select(OutreachRecipient).where(OutreachRecipient.outreach_id == o.id,
                                                         OutreachRecipient.recipient_ref == ref)).scalar_one_or_none()
        if rec is None:
            referral = db.execute(select(Referral).where(Referral.source_system == o.source_system,
                                                         Referral.external_ref == ref)).scalar_one_or_none()
            rec = OutreachRecipient(outreach_id=o.id, recipient_ref=ref, referral_id=referral.id if referral else None,
                                    code=A.unique_code(db, OutreachRecipient, "R", 8))
            db.add(rec)
            db.flush()
        out.append(rec)
    return out


def _outreach_stats(db: DB, o: OutreachMessage) -> dict:
    rows = db.execute(select(ChatSession).where(ChatSession.outreach_id == o.id)).scalars().all()
    journeys = [x for x in rows if not (x.first_touch or {}).get("inherited_from")]
    return {"sessions_started": len(journeys),
            "sessions_completed": sum(1 for x in rows if x.status == "COMPLETED"),
            "unique_whatsapp_users": len({x.wa_id for x in journeys if x.wa_id}),
            "by_channel": {c: sum(1 for x in journeys if x.channel == c) for c in ("whatsapp", "web")},
            "recipients_registered": db.execute(select(func.count()).select_from(OutreachRecipient)
                                                .where(OutreachRecipient.outreach_id == o.id)).scalar()}


def _outreach_view(db: DB, o: OutreachMessage, recipients: list[OutreachRecipient] | None = None) -> dict:
    d = {"message_id": o.message_id, "source_system": o.source_system, "code": o.code, "campaign": o.campaign,
         "channel": o.channel, "template_version": o.template_version, "template_text": o.template_text,
         "sent_at": results.iso(o.sent_at), "created_at": results.iso(o.created_at),
         "links": A.outreach_links(db, o), "whatsapp_number_known": bool(A.wa_number(db)),
         "stats": _outreach_stats(db, o)}
    if recipients is not None:
        d["recipients"] = [{"recipient_ref": r.recipient_ref, "code": r.code, "referral_linked": bool(r.referral_id),
                            **A.outreach_links(db, o, r)} for r in recipients]
    return d


def _get_outreach(db: DB, caller: Caller, message_id: str, source_system: Optional[str]) -> OutreachMessage:
    src = caller.resolve_source(source_system, required=True)
    o = db.execute(select(OutreachMessage).where(OutreachMessage.source_system == src,
                                                 OutreachMessage.message_id == message_id)).scalar_one_or_none()
    if not o:
        _err(404, "outreach_message_not_found", f"No outreach message '{message_id}' for '{src}'.")
    return o


@router.post("/outreach-messages", status_code=201)
def register_outreach(body: OutreachIn, db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    src = caller.resolve_source(body.source_system, required=True)
    ensure_source(db, src)
    o = db.execute(select(OutreachMessage).where(OutreachMessage.source_system == src,
                                                 OutreachMessage.message_id == body.message_id)).scalar_one_or_none()
    if o is None:
        o = OutreachMessage(source_system=src, message_id=body.message_id,
                            code=A.unique_code(db, OutreachMessage, "OM-", 6))
        db.add(o)
    o.campaign, o.channel = body.campaign, body.channel
    o.template_text, o.template_version = body.template_text, body.template_version
    o.sent_at = _parse_since(body.sent_at) if body.sent_at else o.sent_at
    db.flush()
    recs = _add_recipients(db, o, body.recipients or []) if body.recipients else None
    db.commit()
    return _outreach_view(db, o, recs)


@router.post("/outreach-messages/{message_id}/recipients")
def add_outreach_recipients(message_id: str, body: RecipientsIn, source_system: Optional[str] = None,
                            db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    o = _get_outreach(db, caller, message_id, source_system)
    recs = _add_recipients(db, o, body.recipients)
    db.commit()
    return _outreach_view(db, o, recs)


@router.get("/outreach-messages")
def list_outreach(source_system: Optional[str] = None, db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    q = select(OutreachMessage)
    src = caller.resolve_source(source_system)
    if src:
        q = q.where(OutreachMessage.source_system == src)
    rows = db.execute(q.order_by(OutreachMessage.id.desc()).limit(500)).scalars().all()
    return {"count": len(rows), "outreach_messages": [_outreach_view(db, o) for o in rows]}


@router.get("/outreach-messages/{message_id}")
def get_outreach(message_id: str, source_system: Optional[str] = None, include_recipients: bool = False,
                 db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    o = _get_outreach(db, caller, message_id, source_system)
    recs = db.execute(select(OutreachRecipient).where(OutreachRecipient.outreach_id == o.id)
                      .order_by(OutreachRecipient.id)).scalars().all() if include_recipients else None
    return _outreach_view(db, o, recs)


# ------------------------------------------------------------------ results
def _parse_since(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    try:
        dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        _err(400, "invalid_since", "since must be ISO-8601, e.g. 2026-09-28T10:00:00Z")
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


@router.get("/results")
def get_results(source_system: Optional[str] = None, since: Optional[str] = None,
                status: Optional[str] = Query(None, description="ACTIVE, COMPLETED, OPTED_OUT, RESTARTED"),
                channel: Optional[str] = Query(None, pattern="^(whatsapp|web)$"),
                entry_source: Optional[str] = Query(None, pattern="^(OUTREACH|ORGANIC|PEER_REFERRAL)$"),
                limit: int = Query(100, ge=1, le=500),
                db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    q = select(ChatSession)
    if caller.is_admin and source_system == "walk-in":
        q = q.where(ChatSession.source_system.is_(None))
    else:
        src = caller.resolve_source(source_system)
        if src:
            q = q.where(ChatSession.source_system == src)
    dt = _parse_since(since)
    if dt:
        q = q.where(ChatSession.updated_at > dt)
    if status:
        q = q.where(ChatSession.status == status.upper())
    if channel:
        q = q.where(ChatSession.channel == channel)
    if entry_source:
        q = q.where(ChatSession.entry_source == entry_source)
    rows = db.execute(q.order_by(ChatSession.updated_at, ChatSession.id).limit(limit)).scalars().all()
    out = [results.session_result(db, s) for s in rows]
    return {"count": len(out), "next_since": out[-1]["updated_at"] if out else since,
            "has_more": len(out) == limit, "results": out}


# ------------------------------------------------------------------ source system settings (callback)
class SourceIn(BaseModel):
    callback_url: Optional[HttpUrl] = Field(None, description="HTTPS URL that receives discovery.result events; null to remove")
    callback_secret: Optional[str] = Field(None, min_length=16, max_length=200,
                                           description="Shared secret for the X-P2-Signature HMAC header")


def _source_view(db: DB, src: SourceSystem) -> dict:
    counts = dict(db.execute(select(Referral.status, func.count()).where(Referral.source_system == src.name)
                             .group_by(Referral.status)).all())
    return {"source_system": src.name, "callback_url": src.callback_url,
            "callback_secret_set": bool(src.callback_secret), "referrals_by_status": counts}


@router.get("/source-systems/me")
def get_source(source_system: Optional[str] = None, db: DB = Depends(get_db), caller: Caller = Depends(require_api_key)):
    src = ensure_source(db, caller.resolve_source(source_system, required=True))
    db.commit()
    return _source_view(db, src)


@router.put("/source-systems/me")
def put_source(body: SourceIn, source_system: Optional[str] = None, db: DB = Depends(get_db),
               caller: Caller = Depends(require_api_key)):
    src = ensure_source(db, caller.resolve_source(source_system, required=True))
    src.callback_url = str(body.callback_url) if body.callback_url else None
    if body.callback_secret is not None:
        src.callback_secret = body.callback_secret
    db.commit()
    return _source_view(db, src)


# ------------------------------------------------------------------ stateless discovery + metadata
class DiscoverIn(BaseModel):
    state: Optional[str] = None
    class_passed: Optional[str] = None
    category: Optional[str] = None
    gender: Optional[str] = None
    annual_family_income: Optional[Any] = None
    dob: Optional[str] = None
    limit: int = Field(10, ge=1, le=200)
    include_audit: bool = False


@router.post("/discover")
def discover(body: DiscoverIn, caller: Caller = Depends(require_api_key)):
    facts, warns = F.normalise_facts(body.model_dump())
    res = get_engine().evaluate(facts)
    out = {"facts_used": facts, "warnings": warns, "rule_version": res["rule_version"], "as_of": res["as_of"],
           "candidate_schemes_checked": res["candidate_schemes_checked"], "eligible_count": res["eligible_count"],
           "schemes": res["schemes"][: body.limit]}
    if body.include_audit:
        out["audit"] = res["audit"]
    return out


@router.get("/meta")
def meta(caller: Caller = Depends(require_api_key)):
    e = get_engine()
    return {"api_version": "v1", "rule_version": "V3.0", "schemes_total": len(e.all_rules), "schemes_active": len(e.rules),
            "questions_asked": e.needed_facts(), "states": e.states(), "categories": F.CATEGORIES,
            "genders": F.GENDERS, "class_passed": ["PRE", "X", "XII", "UG", "PG"], "reasons": sorted(REASONS),
            "entry_sources": ["OUTREACH", "ORGANIC", "PEER_REFERRAL"], "whatsapp_number": A.wa_number(None) or None,
            "referral_fields": FIELDS, "languages": LANG_CODES}
