"""Speech providers. Pick one with SPEECH_PROVIDER (see app/speech/__init__.py)."""
from __future__ import annotations

import base64
import io
import logging
import struct
import wave

from ..config import settings
from .base import (SpeechError, SpeechNotConfigured, SpeechNotImplemented, SpeechProvider, STTResult, TTSResult)

log = logging.getLogger(__name__)

# App language code -> BCP-47 tag most vendors accept (Bhojpuri / Maithili fall back to Hindi voices).
BCP47 = {"en": "en-IN", "hi": "hi-IN", "bn": "bn-IN", "as": "as-IN", "kn": "kn-IN", "ta": "ta-IN", "te": "te-IN",
         "ml": "ml-IN", "or": "or-IN", "bho": "hi-IN", "mai": "hi-IN", "gu": "gu-IN", "mr": "mr-IN", "pa": "pa-IN"}


def _client(timeout: float = 30.0):
    from ..results import http_client          # shares the test transport (no real HTTP in tests)
    return http_client(timeout=timeout)


class NoProvider(SpeechProvider):
    name = "none"

    def tts(self, text, lang="en", voice=None):
        raise SpeechNotConfigured("Speech is not configured (set SPEECH_ENABLED=true and SPEECH_PROVIDER).")

    def stt(self, audio, mime="audio/ogg", lang=None):
        raise SpeechNotConfigured("Speech is not configured (set SPEECH_ENABLED=true and SPEECH_PROVIDER).")


def silent_wav(seconds: float = 0.6, rate: int = 8000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))
    return buf.getvalue()


class MockProvider(SpeechProvider):
    """For local demos and tests: no network, no cost."""
    name = "mock"

    def tts(self, text, lang="en", voice=None):
        return TTSResult(audio=silent_wav(), mime="audio/wav", provider=self.name, meta={"chars": len(text), "lang": lang})

    def stt(self, audio, mime="audio/ogg", lang=None):
        return STTResult(text="I am in 2nd year BA", language=lang or "en", confidence=1.0, provider=self.name,
                         meta={"bytes": len(audio)})


class HttpGatewayProvider(SpeechProvider):
    """Generic gateway (contract in docs/SPEECH_API.md):

    POST {SPEECH_API_URL}/tts  JSON {"text", "lang", "bcp47", "voice"}  -> audio bytes (Content-Type audio/*)
                                                                          or JSON {"audio_base64", "mime"} / {"url"}
    POST {SPEECH_API_URL}/stt  multipart file=<audio>, lang, bcp47       -> JSON {"text", "confidence"?, "language"?}
    Auth: "Authorization: Bearer {SPEECH_API_KEY}" when a key is set.
    """
    name = "http"

    def _base(self) -> str:
        if not settings.speech_api_url:
            raise SpeechNotConfigured("SPEECH_API_URL is not set for SPEECH_PROVIDER=http.")
        return settings.speech_api_url.rstrip("/")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {settings.speech_api_key}"} if settings.speech_api_key else {}

    def tts(self, text, lang="en", voice=None):
        url = self._base() + "/tts"
        try:
            with _client() as c:
                r = c.post(url, json={"text": text, "lang": lang, "bcp47": BCP47.get(lang, "en-IN"), "voice": voice},
                           headers=self._headers())
        except Exception as e:  # noqa: BLE001
            raise SpeechError(f"TTS gateway unreachable: {type(e).__name__}") from e
        if r.status_code >= 400:
            raise SpeechError(f"TTS gateway HTTP {r.status_code}")
        ctype = r.headers.get("content-type", "")
        if ctype.startswith("audio/"):
            return TTSResult(audio=r.content, mime=ctype.split(";")[0], provider=self.name)
        j = r.json()
        if j.get("audio_base64"):
            return TTSResult(audio=base64.b64decode(j["audio_base64"]), mime=j.get("mime", "audio/mpeg"), provider=self.name)
        if j.get("url"):
            return TTSResult(url=j["url"], mime=j.get("mime", "audio/mpeg"), provider=self.name)
        raise SpeechError("TTS gateway returned no audio")

    def stt(self, audio, mime="audio/ogg", lang=None):
        url = self._base() + "/stt"
        try:
            with _client() as c:
                r = c.post(url, files={"file": ("audio", audio, mime)},
                           data={"lang": lang or "", "bcp47": BCP47.get(lang or "en", "en-IN")}, headers=self._headers())
        except Exception as e:  # noqa: BLE001
            raise SpeechError(f"STT gateway unreachable: {type(e).__name__}") from e
        if r.status_code >= 400:
            raise SpeechError(f"STT gateway HTTP {r.status_code}")
        j = r.json()
        return STTResult(text=(j.get("text") or "").strip(), language=j.get("language") or lang,
                         confidence=j.get("confidence"), provider=self.name)


class _Placeholder(SpeechProvider):
    """Named vendor placeholder. `docs` records the endpoint / auth shape for whoever finishes the adapter."""
    docs = ""

    def tts(self, text, lang="en", voice=None):
        raise SpeechNotImplemented(f"{self.name} TTS adapter is not implemented yet (integration later). {self.docs}")

    def stt(self, audio, mime="audio/ogg", lang=None):
        raise SpeechNotImplemented(f"{self.name} STT adapter is not implemented yet (integration later). {self.docs}")


class BhashiniProvider(_Placeholder):
    name = "bhashini"
    docs = ("Bhashini ULCA pipeline: get pipeline config (userID + ulcaApiKey), then call the inference endpoint "
            "with taskType 'tts' / 'asr'. SPEECH_API_URL = inference URL, SPEECH_API_KEY = 'userID:ulcaApiKey'.")


class GoogleProvider(_Placeholder):
    name = "google"
    docs = ("Google Cloud Text-to-Speech v1 text:synthesize and Speech-to-Text v2 recognize. "
            "SPEECH_API_KEY = API key or service-account token.")


class ElevenLabsProvider(_Placeholder):
    name = "elevenlabs"
    docs = ("ElevenLabs /v1/text-to-speech/{voice_id} (xi-api-key header) and /v1/speech-to-text. "
            "SPEECH_API_KEY = xi-api-key; voice per language to be chosen.")


class SarvamProvider(_Placeholder):
    name = "sarvam"
    docs = ("Sarvam AI /text-to-speech and /speech-to-text (api-subscription-key header), Indian languages. "
            "SPEECH_API_KEY = subscription key.")


PROVIDERS = {p.name: p for p in (NoProvider, MockProvider, HttpGatewayProvider, BhashiniProvider, GoogleProvider,
                                 ElevenLabsProvider, SarvamProvider)}


def get_provider() -> SpeechProvider:
    if not settings.speech_ready:
        return NoProvider()
    cls = PROVIDERS.get(settings.speech_provider)
    if cls is None:
        log.warning("Unknown SPEECH_PROVIDER=%s - speech disabled", settings.speech_provider)
        return NoProvider()
    return cls()


def speech_status() -> dict:
    """What the web companion needs to know (no secrets)."""
    p = get_provider()
    implemented = not isinstance(p, (NoProvider, _Placeholder))
    return {"enabled": settings.speech_enabled, "provider": settings.speech_provider,
            "tts": implemented and p.supports_tts, "stt": implemented and p.supports_stt,
            "configured": implemented,
            "max_chars": settings.speech_max_chars}
