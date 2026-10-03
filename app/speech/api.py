"""Speech endpoints (Update 3 provision - off by default).

GET  /v1/speech/status   {"enabled", "provider", "tts", "stt", "configured", "max_chars"}
POST /v1/speech/tts      JSON {"text", "lang", "voice"?}  -> {"audio_base64", "mime", "url", "provider"}
POST /v1/speech/stt      multipart: file=<audio>, lang=<code>  -> {"text", "language", "confidence", "provider"}

When speech is off (SPEECH_ENABLED=false or SPEECH_PROVIDER=none) both calls answer
503 {"error": "speech_not_configured", ...} so the web companion can fall back (browser voice / hide the mic).
Public like the companion itself, with a simple per-IP limit (SPEECH_RATE_LIMIT calls per 10 minutes, default 40)
so a paid provider cannot be run up by one caller. Put a real gateway / quota in front before going to scale.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..config import settings
from .base import SpeechError, SpeechNotConfigured, SpeechNotImplemented
from .providers import get_provider, speech_status

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/speech", tags=["speech (TTS / STT)"])
LANG_PATTERN = "^(en|hi|bn|as|kn|ta|te|ml|or|bho|mai|gu|mr|pa)$"


_CALLS: dict = defaultdict(deque)


def _limit(request: Request) -> None:
    """In-memory per-IP limit (one Render instance). Only applies when speech is actually on."""
    try:
        cap = int(os.environ.get("SPEECH_RATE_LIMIT", "40") or 40)
    except ValueError:
        cap = 40
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now, q = time.time(), _CALLS[ip]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= cap:
        raise HTTPException(429, detail={"error": "speech_rate_limited", "message": "Too many speech requests. Try later."})
    q.append(now)


class TTSIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    lang: str = Field("en", pattern=LANG_PATTERN)
    voice: Optional[str] = Field(None, max_length=60)


def _err(e: SpeechError) -> HTTPException:
    code = getattr(e, "code", "speech_failed")
    status = 503 if isinstance(e, (SpeechNotConfigured, SpeechNotImplemented)) else 502
    msg = str(e) or {"speech_not_configured": "Speech (TTS/STT) is not configured on this server.",
                     "speech_provider_not_implemented": "This speech provider is a placeholder (integration later)."
                     }.get(code, "Speech provider error")
    return HTTPException(status, detail={"error": code, "message": msg, "provider": settings.speech_provider})


@router.get("/status")
def status():
    return speech_status()


@router.post("/tts")
def tts(body: TTSIn, request: Request):
    if settings.speech_ready:
        _limit(request)
    text = body.text[: settings.speech_max_chars]
    try:
        r = get_provider().tts(text, lang=body.lang, voice=body.voice)
    except SpeechError as e:
        raise _err(e)
    except Exception as e:  # noqa: BLE001
        log.warning("TTS failed: %s", e)
        raise _err(SpeechError(f"TTS failed: {type(e).__name__}"))
    return {"provider": r.provider, "mime": r.mime, "url": r.url, "truncated": len(body.text) > len(text),
            "audio_base64": base64.b64encode(r.audio).decode() if r.audio else None}


@router.post("/stt")
async def stt(request: Request, file: UploadFile = File(...), lang: Optional[str] = Form(None)):
    if not settings.speech_ready:
        raise _err(SpeechNotConfigured("Speech (TTS/STT) is not configured on this server."))
    _limit(request)
    audio = await file.read()
    if not audio:
        raise HTTPException(400, detail={"error": "empty_audio", "message": "No audio received."})
    if len(audio) > settings.speech_max_audio_bytes:
        raise HTTPException(413, detail={"error": "audio_too_large", "message": "Audio is too long."})
    try:
        r = get_provider().stt(audio, mime=file.content_type or "audio/webm", lang=lang)
    except SpeechError as e:
        raise _err(e)
    except Exception as e:  # noqa: BLE001
        log.warning("STT failed: %s", e)
        raise _err(SpeechError(f"STT failed: {type(e).__name__}"))
    return {"text": r.text, "language": r.language or lang, "confidence": r.confidence, "provider": r.provider}
