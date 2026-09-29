"""Simple admin page served by FastAPI (no second Render service needed).

Open https://<service>.onrender.com/admin ; browser asks for a login:
user name: anything (e.g. admin), password: the P2_API_KEY value from the env group.
Mobile numbers are always masked.
"""
from __future__ import annotations

import hmac
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from .config import settings
from .db import ChatSession, Message, OutreachMessage, Referral, Suggestion, get_db
from .facts import mask_mobile
from datetime import timedelta


def iso(dt):
    """Admin page shows India time (IST, UTC+5:30); the API always returns UTC."""
    return (dt + timedelta(hours=5, minutes=30)).strftime("%d %b %Y %H:%M IST") if dt else ""

router = APIRouter(tags=["admin"])
basic = HTTPBasic(auto_error=False)


def admin_auth(creds: HTTPBasicCredentials | None = Depends(basic)):
    if not settings.admin_api_key:
        raise HTTPException(503, "Admin page disabled: set P2_API_KEY")
    if not creds or not hmac.compare_digest(creds.password or "", settings.admin_api_key):
        raise HTTPException(401, "Login with password = P2_API_KEY", headers={"WWW-Authenticate": 'Basic realm="mosje-p2"'})


def _table(headers, rows) -> str:
    th = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{escape(str(c if c is not None else ''))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs or '<tr><td colspan=99><i>none yet</i></td></tr>'}</tbody></table>"


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page(db: DB = Depends(get_db), _=Depends(admin_auth)):
    ref_counts = db.execute(select(Referral.source_system, Referral.status, func.count())
                            .group_by(Referral.source_system, Referral.status)).all()
    by_src: dict = {}
    for src, st, n in ref_counts:
        by_src.setdefault(src, {})[st] = n
    statuses = ["RECEIVED", "INVITED", "IN_CONVERSATION", "COMPLETED", "CONSENT_DECLINED", "OPTED_OUT"]
    ref_rows = [[src] + [d.get(s, 0) for s in statuses] + [sum(d.values())] for src, d in sorted(by_src.items())]

    sess_counts = db.execute(select(ChatSession.channel, ChatSession.status, func.count())
                             .group_by(ChatSession.channel, ChatSession.status)).all()
    sess_rows = [[c, s, n] for c, s, n in sess_counts]

    recent = db.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(30)).scalars().all()
    recent_rows = []
    for s in recent:
        ref = db.get(Referral, s.referral_id) if s.referral_id else None
        a = {k: v for k, v in (s.answers or {}).items() if not k.startswith("_")}
        recent_rows.append([s.public_id, s.channel, s.entry_source, s.source_system or "walk-in", ref.external_ref if ref else "",
                            mask_mobile(s.wa_id), s.language, s.state, s.status, s.eligible_count,
                            ", ".join(f"{k}={v}" for k, v in a.items()), iso(s.updated_at)])

    sugg = db.execute(select(Suggestion, ChatSession).join(ChatSession, Suggestion.session_id == ChatSession.id)
                      .where(Suggestion.rank <= 3).order_by(Suggestion.id.desc()).limit(30)).all()
    sugg_rows = [[iso(x.created_at), c.channel, c.source_system or "walk-in", mask_mobile(c.wa_id), x.rank,
                  x.scheme_id, x.scheme_name] for x, c in sugg]
    entry_counts = db.execute(select(ChatSession.entry_source, ChatSession.channel, func.count())
                              .group_by(ChatSession.entry_source, ChatSession.channel)).all()
    entry_rows = [[e, c, n] for e, c, n in sorted(entry_counts, key=lambda r: (r[0] or "", r[1] or ""))]

    om_rows = []
    for o in db.execute(select(OutreachMessage).order_by(OutreachMessage.id.desc()).limit(30)).scalars().all():
        ss = db.execute(select(ChatSession).where(ChatSession.outreach_id == o.id)).scalars().all()
        started = [x for x in ss if not (x.first_touch or {}).get("inherited_from")]
        om_rows.append([o.source_system, o.message_id, o.code, o.campaign, o.channel, iso(o.sent_at), len(started),
                        sum(1 for x in ss if x.status == "COMPLETED")])

    referrers = db.execute(select(ChatSession).where(ChatSession.share_code.is_not(None))
                           .order_by(ChatSession.id.desc()).limit(200)).scalars().all()
    ref_rows_peer = []
    for r in referrers:
        kids = db.execute(select(ChatSession.first_touch).where(ChatSession.referrer_session_id == r.id)).scalars().all()
        n = sum(1 for ft in kids if not (ft or {}).get("inherited_from"))
        ref_rows_peer.append([r.share_code, r.channel, mask_mobile(r.wa_id) or r.public_id, r.feedback_rating, n])
    ref_rows_peer.sort(key=lambda x: -x[4])
    fb = db.execute(select(func.count(ChatSession.feedback_rating), func.avg(ChatSession.feedback_rating))).one()

    msg_counts = db.execute(select(Message.channel, Message.direction, func.count())
                            .group_by(Message.channel, Message.direction)).all()
    wa = "configured ✅" if settings.whatsapp_configured else "NOT configured (replies are logged, not sent)"
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>MoSJE P2 admin</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:system-ui,Arial,sans-serif;margin:24px;color:#1f2937}}h1{{font-size:22px}}h2{{font-size:17px;margin-top:28px}}
table{{border-collapse:collapse;font-size:13px;width:100%}}th,td{{border:1px solid #e5e7eb;padding:5px 7px;text-align:left;vertical-align:top}}
th{{background:#f3f4f6}}.note{{color:#6b7280;font-size:13px}}</style></head><body>
<h1>MoSJE Product 2 – Scholarship Discovery Assistant (admin)</h1>
<p class="note">SYNTHETIC / TEST DATA ONLY. WhatsApp sending: {wa}. Mobile numbers are masked. <a href="/docs">API docs</a> · <a href="/companion">Web companion</a></p>
<h2>Referrals per source system</h2>{_table(["source_system"] + statuses + ["total"], ref_rows)}
<h2>Sessions by channel and status</h2>{_table(["channel", "status", "count"], sess_rows)}
<h2>Sessions by entry source</h2>{_table(["entry_source", "channel", "sessions"], entry_rows)}
<h2>Outreach messages (30 latest)</h2>{_table(["source", "message_id", "code", "campaign", "channel", "sent_at", "journeys started", "completed"], om_rows)}
<h2>Peer referrers (share codes)</h2><p class="note">Feedback given: {fb[0]} · average rating: {round(fb[1], 2) if fb[1] else "–"}</p>
{_table(["share_code", "channel", "referrer", "their rating", "friends who started"], ref_rows_peer[:30])}
<h2>Messages</h2>{_table(["channel", "direction", "count"], [list(r) for r in msg_counts])}
<h2>Recent sessions (30)</h2>{_table(["session", "channel", "entry", "source", "external_ref", "mobile", "lang", "state", "status", "eligible", "answers", "updated"], recent_rows)}
<h2>Recent suggestions (top 3 per session)</h2>{_table(["at", "channel", "source", "mobile", "rank", "scheme_id", "scheme"], sugg_rows)}
</body></html>"""
    return HTMLResponse(html)
