# Product 2 – Text-to-speech / speech-to-text provision (integration later)

Status: **built and switched off.** No speech vendor is connected yet. The endpoints, the web buttons and the WhatsApp voice-note hook are all in place. A vendor can be plugged in later by setting environment variables and, for some vendors, adding one small adapter class. No other code needs to change.

## 1. What the student sees today (speech off)

| Where | Speech off (now) | Speech on (later) |
|---|---|---|
| Web companion – **Listen** on a scheme | The phone's own voice reads the scheme aloud, if the browser has one. Otherwise a short message appears. | The server voice (`POST /v1/speech/tts`) in the student's language |
| Web companion – **mic** button (empty message box) | Toast: “Voice typing is coming soon – please type for now” | Records up to 10 seconds → `POST /v1/speech/stt` → the text is treated as a typed answer (with the usual “You mean …?” check) |
| WhatsApp – voice note | Reply: “🎤 Voice notes are coming soon. Please type your answer for now.” | The voice note is downloaded from Meta, sent to STT, and the bot replies “🎤 I heard: …” followed by the normal answer |

## 2. Settings (Render → mosje-p2-api → Environment)

| Variable | Default | Meaning |
|---|---|---|
| `SPEECH_ENABLED` | `false` | Master switch. Keep `false` until a vendor is contracted. |
| `SPEECH_PROVIDER` | `none` | `none`, `mock` (local tests only: silent audio, fixed text), `http` (your own gateway, see 4), or the placeholders `bhashini`, `google`, `elevenlabs`, `sarvam` |
| `SPEECH_API_KEY` | – | Vendor or gateway key (secret). |
| `SPEECH_API_URL` | – | Vendor or gateway base URL. |
| `SPEECH_MAX_CHARS` | `1500` | Longest text sent to TTS in one call. Longer text is cut, and `truncated: true` is returned. |
| `SPEECH_RATE_LIMIT` | `40` | Speech calls allowed per IP address per 10 minutes. This protects a paid vendor account. |

The placeholders (`bhashini`, `google`, `elevenlabs`, `sarvam`) are not written yet. If one of them is selected, the API answers `503 speech_provider_not_implemented`. To add one, write a class in `app/speech/providers.py` with `tts()` and `stt()` methods (copy `HttpGatewayProvider`) and register it in `PROVIDERS`. Language codes are already mapped to BCP-47 (`hi` → `hi-IN`; Bhojpuri and Maithili fall back to Hindi voices).

## 3. API

`GET /v1/speech/status` → `{"enabled": false, "provider": "none", "configured": false, "tts": false, "stt": false, "max_chars": 1500}`

`POST /v1/speech/tts`, JSON `{"text": "…", "lang": "hi", "voice": null}` →
`{"provider": "http", "mime": "audio/mpeg", "audio_base64": "…", "url": null, "truncated": false}`.
The answer carries either `audio_base64` or `url`.

`POST /v1/speech/stt`, multipart `file=<audio>` (webm, ogg, mp3 or wav; at most 5 MB), `lang=hi` →
`{"text": "मैं बीए दूसरे साल में हूँ", "language": "hi", "confidence": 0.91, "provider": "http"}`

Errors (all `{"detail": {"error", "message", "provider"}}`):

| HTTP | error | When |
|---|---|---|
| 503 | `speech_not_configured` | `SPEECH_ENABLED` is false, the provider is `none`, or the URL/key is missing |
| 503 | `speech_provider_not_implemented` | A placeholder provider is selected |
| 502 | `speech_failed` | The vendor failed or could not be reached |
| 400 / 413 | `empty_audio` / `audio_too_large` | Bad upload |
| 429 | `speech_rate_limited` | Over `SPEECH_RATE_LIMIT` |
| 422 | – | Empty text or an unknown language code |

## 4. `http` gateway contract (the quickest way to connect any vendor)

If `SPEECH_PROVIDER=http`, Product 2 calls your gateway at `SPEECH_API_URL`. When a key is set, it sends `Authorization: Bearer <SPEECH_API_KEY>`.

* `POST {SPEECH_API_URL}/tts` with JSON `{"text", "lang", "bcp47", "voice"}`. The gateway answers with raw audio (`Content-Type: audio/*`), or JSON `{"audio_base64", "mime"}`, or JSON `{"url", "mime"}`.
* `POST {SPEECH_API_URL}/stt` with multipart `file`, `lang`, `bcp47`. The gateway answers with JSON `{"text", "confidence"?, "language"?}`.

So a small gateway (for example a Bhashini ULCA pipeline wrapper or a Google Cloud function) can be swapped in without changing Product 2.

## 5. WhatsApp voice notes

`app/channels/whatsapp.py` turns an incoming `audio` / `voice` message into an internal marker. When speech is on, `voice_to_text()` downloads the media from the Graph API (`GET /{media-id}`, then the file URL, using `WHATSAPP_TOKEN`) and calls `stt()`. The recognised text then goes through the normal conversation flow, including typed-answer understanding. When speech is off, the student gets the `voice_soon` message in their language.

## 6. Before switching on

1. Choose the vendor and languages, and sign the data-processing terms. Voice is personal data: keep audio only in memory, as the code does now, and do not log it.
2. Set `SPEECH_PROVIDER` / `SPEECH_API_URL` / `SPEECH_API_KEY`, then `SPEECH_ENABLED=true`, then Manual Deploy.
3. Check `/health` (it should show `"speech_enabled": true`) and `/v1/speech/status`.
4. Test Listen and the mic on a real phone in Hindi and one other language.
