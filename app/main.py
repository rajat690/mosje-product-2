"""MoSJE Product 2 – Scholarship Discovery Assistant (WhatsApp + web companion).

Standalone service: it does not import Product 1. Product 1 systems connect through the
versioned integration contract under /v1 (see INTEGRATION_SPEC.md).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from sqlalchemy import text

from . import db as dbm
from .admin import router as admin_router
from .channels.web import router as web_router
from .companion_api import jobs as jobs_router
from .companion_api import router as companion_router
from .speech.api import router as speech_router
from .channels.whatsapp import router as wa_router
from .config import settings
from .eligibility import get_engine
from .integration import router as v1_router

__version__ = "1.0.0"
STATIC = Path(__file__).resolve().parent / "static"
log = logging.getLogger("mosje_p2")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=settings.log_level)
    dbm.init_engine()                 # creates tables if they do not exist
    e = get_engine()
    log.info("P2 started: %d schemes (%d active), WhatsApp configured=%s", len(e.all_rules), len(e.rules),
             settings.whatsapp_configured)
    yield


app = FastAPI(
    title="MoSJE Product 2 – Scholarship Discovery Assistant",
    version=__version__,
    description=("WhatsApp + web chat discovery assistant using Scholarship Eligibility Rule V3.0. "
                 "Integration contract for Product 1 systems is under /v1 (X-API-Key). "
                 "SYNTHETIC / TEST DATA ONLY on this hosting."),
    lifespan=lifespan,
)

if settings.allowed_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                       allow_headers=["Content-Type", "X-API-Key", "X-Session-Token", "X-Student-Token",
                                      "Authorization"],
                       allow_credentials=False)

app.include_router(wa_router)
app.include_router(v1_router)
app.include_router(web_router)
app.include_router(admin_router)
app.include_router(companion_router)
app.include_router(jobs_router)
app.include_router(speech_router)


def _frame_headers() -> dict:
    """Allow the companion to be embedded in iframes; restrict to ALLOWED_ORIGINS when set."""
    if settings.allowed_origins and "*" not in settings.allowed_origins:
        return {"Content-Security-Policy": "frame-ancestors 'self' " + " ".join(settings.allowed_origins)}
    return {}


@app.get("/", include_in_schema=False)
def root():
    return {"service": "mosje-p2-api", "version": __version__, "docs": "/docs", "health": "/health",
            "companion": "/companion", "companion_classic": "/companion/classic", "admin": "/admin", "integration": "/v1 (see INTEGRATION_SPEC.md)"}


@app.get("/health", tags=["ops"])
def health():
    db_ok = True
    try:
        with dbm.engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    e = get_engine()
    return JSONResponse({"status": "ok" if db_ok else "degraded", "version": __version__, "database": db_ok,
                         "db_kind": dbm.engine.dialect.name, "schemes_active": len(e.rules), "rule_version": "V3.0",
                         "whatsapp_configured": settings.whatsapp_configured,
                         "whatsapp_signature_check": bool(settings.wa_app_secret),
                         "api_keys_configured": bool(settings.admin_api_key or settings.source_keys),
                         "source_systems_with_keys": sorted(set(settings.source_keys.values())),
                         "companion_public": settings.companion_public,
                         "speech_enabled": settings.speech_ready, "speech_provider": settings.speech_provider,
                         "whatsapp_web_link": settings.wa_web_link},
                        status_code=200 if db_ok else 503)


COMPANION_DIR = STATIC / "companion"
_PAGE_CACHE: dict = {}


def companion_page() -> str:
    """Update 3: the mobile-first, WhatsApp-native companion - one HTML response (CSS + JS inlined, no external
    requests, well under 200 KB) assembled from app/static/companion/*."""
    files = ["index.html", "styles.css", "strings.js", "icons.js", "app.js"]
    stamp = tuple((COMPANION_DIR / f).stat().st_mtime for f in files)
    if _PAGE_CACHE.get("stamp") != stamp:
        read = lambda f: (COMPANION_DIR / f).read_text(encoding="utf-8")
        html = read("index.html")
        html = html.replace("/*__CSS__*/", read("styles.css"))
        html = html.replace("//__JS__", "\n".join(read(f) for f in files[2:]))
        _PAGE_CACHE.update(stamp=stamp, html=html)
    return _PAGE_CACHE["html"]


@app.get("/companion", include_in_schema=False)
def companion():
    return HTMLResponse(companion_page(), headers=_frame_headers())


@app.get("/companion/lang/{code}.json", include_in_schema=False)
def companion_lang(code: str):
    """2 Oct: UI language pack for the companion (strings, document help, month names, State names), loaded on demand
    so the first page stays small. 404 = no pack yet -> the page uses English for the app chrome."""
    from .conversation.texts import LANGS
    f = COMPANION_DIR / "lang" / f"{code}.json"
    if code not in LANGS or not f.is_file():
        raise HTTPException(404, "No UI language pack for this language yet")
    return FileResponse(f, media_type="application/json; charset=utf-8",
                        headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"})


@app.get("/companion/classic", include_in_schema=False)
def companion_classic():
    """The Update 1-2 chat-style companion, kept for comparison / fallback."""
    return HTMLResponse((STATIC / "companion.html").read_text(encoding="utf-8"), headers=_frame_headers())


@app.get("/companion/embed.js", include_in_schema=False)
def embed_js():
    return FileResponse(STATIC / "embed.js", media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300", "Access-Control-Allow-Origin": "*"})


@app.get("/companion/demo", include_in_schema=False)
def embed_demo(request: Request):
    base = settings.public_base_url or str(request.base_url).rstrip("/")
    return HTMLResponse((STATIC / "embed_demo.html").read_text(encoding="utf-8").replace("__BASE__", base))
