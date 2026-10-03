"""Speech provider interface."""
from __future__ import annotations

from dataclasses import dataclass, field


class SpeechError(Exception):
    """A provider call failed (network, quota, bad audio ...)."""
    code = "speech_failed"


class SpeechNotConfigured(SpeechError):
    """SPEECH_ENABLED is off or SPEECH_PROVIDER is 'none' / missing credentials."""
    code = "speech_not_configured"


class SpeechNotImplemented(SpeechError):
    """The named provider is a placeholder - adapter still to be written (integration later)."""
    code = "speech_provider_not_implemented"


@dataclass
class TTSResult:
    audio: bytes = b""
    mime: str = "audio/mpeg"
    url: str | None = None            # some providers return a hosted URL instead of bytes
    provider: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class STTResult:
    text: str = ""
    language: str | None = None
    confidence: float | None = None
    provider: str = ""
    meta: dict = field(default_factory=dict)


class SpeechProvider:
    """Implement tts() and stt(). Language codes are the app's codes: en hi bn as kn ta te ml or bho mai gu mr pa."""
    name = "base"
    supports_tts = True
    supports_stt = True

    def tts(self, text: str, lang: str = "en", voice: str | None = None) -> TTSResult:  # pragma: no cover
        raise NotImplementedError

    def stt(self, audio: bytes, mime: str = "audio/ogg", lang: str | None = None) -> STTResult:  # pragma: no cover
        raise NotImplementedError
