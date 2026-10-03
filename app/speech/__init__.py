"""Provider-agnostic speech (TTS / STT) provision - Update 3.

Off by default (SPEECH_ENABLED=false). Choose a provider with SPEECH_PROVIDER and give SPEECH_API_KEY /
SPEECH_API_URL. Everything else in the app talks only to `get_provider()`:

    from app.speech import get_provider, SpeechNotConfigured
    audio = get_provider().tts("नमस्ते", lang="hi")         # -> TTSResult(audio=bytes, mime="audio/mpeg")
    text = get_provider().stt(raw_bytes, mime="audio/ogg", lang="hi").text

Providers (app/speech/providers.py):
    none        default - every call raises SpeechNotConfigured (the API answers 503 "speech_not_configured")
    mock        local testing - TTS returns a short silent WAV, STT returns a fixed transcript
    http        generic gateway you host (contract in docs/SPEECH_API.md) - works with any vendor behind it
    bhashini, google, elevenlabs, sarvam
                named placeholders with the vendor's endpoint / auth shape written down;
                they raise SpeechNotImplemented until the integration is finished (integration later)
"""
from .base import (SpeechError, SpeechNotConfigured, SpeechNotImplemented, SpeechProvider, STTResult,  # noqa: F401
                   TTSResult)
from .providers import PROVIDERS, get_provider, speech_status  # noqa: F401
