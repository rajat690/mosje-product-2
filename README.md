# MoSJE Product 2 – Scholarship Discovery Assistant

WhatsApp + web chat companion that helps students (Class 1 to Post Graduation) discover government scholarships using **Scholarship Eligibility Rule V3.0** and the **547-row MoSJE Scholarship Master V3.0**.

* **Standalone.** It does not import or depend on Product 1. Product 1 systems (for example `p1-rajat`, `p1-teamB`) connect through the versioned **integration contract** in [INTEGRATION_SPEC.md](INTEGRATION_SPEC.md).
* **Channel-agnostic conversation engine** (`app/conversation/`), with adapters for **WhatsApp** (Meta Cloud API) and the **web** (REST chat API + embeddable `/companion` widget).
* **Own eligibility engine** (`app/eligibility/`): the V3.0 checks, copied from the Product 1 reference code, with the scheme master shipped as data (`data/`).
* **Entry-source attribution** on every session: `OUTREACH` (registered outreach message links), `ORGANIC`, `PEER_REFERRAL` (refer-a-friend codes `REF-…`, offered after feedback and in My schemes).
* **Mobile-first, WhatsApp-style web companion** (Update 3, Product Vision V1.0): typed answers understood, review card with per-answer Edit, summary with filters, scheme details with documents checklist, **Save on WhatsApp** (one tap when opened from WhatsApp; “Hi + code” for anonymous web users; parent OK for under-18), **My schemes** with application tracker and last-date / renewal reminders, new-scheme alerts, feedback and refer a friend.
* **Page in 7 languages** (2 Oct): English, Hindi, Bengali, Marathi, Tamil, Telugu, Kannada (Bhojpuri / Maithili use Hindi labels), State names in the student's script, summary shows **“Up to ₹X a year”** (biggest single scheme, never a sum). Machine-drafted – see [docs/COMPANION_TRANSLATIONS.md](docs/COMPANION_TRANSLATIONS.md).
* **Speech provision** (`app/speech/`): text-to-speech / speech-to-text API, switched **off** until a vendor is chosen ([docs/SPEECH_API.md](docs/SPEECH_API.md)).
* **SYNTHETIC / TEST DATA ONLY** on this hosting. Real data must stay on NIC / MeghRaj.

Setup for non-developers: [SETUP_GUIDE.md](SETUP_GUIDE.md) (also .docx).

## Endpoints (summary)

| Path | Purpose |
|---|---|
| `GET /health`, `GET /docs` | Health and interactive API docs (work even without WhatsApp settings) |
| `GET/POST /whatsapp/webhook` | Meta verification + inbound messages/statuses (signature check if `WHATSAPP_APP_SECRET` is set; idempotent on message id) |
| `POST /whatsapp/send-template` | Admin-key test sender (`hello_world`) |
| `POST /v1/referrals`, `POST /v1/referrals/upload`, `GET /v1/referrals/{ref}`, `POST /v1/referrals/{ref}/invite` | Referral intake (JSON / CSV / XLSX), lookup, WhatsApp invite |
| `POST/GET /v1/outreach-messages…` | Outreach message registry + trackable wa.me / web links (per message and per recipient) |
| `GET /v1/results` | Results feed (answers, schemes, channel, entry source, feedback), `since` cursor |
| `GET/PUT /v1/source-systems/me` | Callback URL + secret per source system |
| `POST /v1/discover`, `GET /v1/meta` | Stateless eligibility check; controlled values |
| `POST /v1/chat/sessions`, `POST /v1/chat/sessions/{id}/messages`, `GET /v1/chat/sessions/{id}` | Web chat API (structured replies: options + scheme cards) |
| `GET /companion`, `/companion/classic`, `/companion/embed.js`, `/companion/demo` | New mobile companion (Update 3), the previous chat page, embed snippet, demo host page |
| `GET /companion/lang/{code}.json` | Page language pack (labels, document help, months, State names) – `bn`, `mr`, `ta`, `te`, `kn`, `hi` (States) |
| `GET /v1/companion/config`, `POST /v1/companion/open` | Companion settings (languages, states, speech, WhatsApp link); open a one-time WhatsApp link (`?c=WL-…`) |
| `POST /v1/companion/sessions/{id}/interpret`, `GET …/results`, `GET …/schemes/{scheme_id}`, `POST …/events` | Typed-answer check (“You mean …?”), summary + scheme cards, scheme detail, UI events (`X-Session-Token`) |
| `POST /v1/companion/sessions/{id}/feedback`, `POST …/referral` | Feedback (1–5 + comment + context) → refer-a-friend links; refer links / share log |
| `POST /v1/companion/sessions/{id}/save`, `GET …/save-status/{code}` | Save on WhatsApp (one tap, `SAVE-` code, or parent `OK-` code) and polling |
| `GET/DELETE /v1/companion/me`, `PUT /v1/companion/me/preferences`, `POST/PATCH/DELETE /v1/companion/me/schemes…`, `POST /v1/companion/me/referral` | My schemes, tracker, dates, reminder settings, delete my data (`X-Student-Token`) |
| `GET /v1/companion/feedback`, `GET /v1/companion/funnel` | Partner views (API key, tenant-scoped): feedback list, funnel counts |
| `POST /v1/jobs/run-reminders` | Admin key: send due reminders and new-scheme alerts (call once a day) |
| `GET /v1/speech/status`, `POST /v1/speech/tts`, `POST /v1/speech/stt` | Speech provision (503 `speech_not_configured` while off) |
| `GET /admin` | Admin page (HTTP Basic, password = `P2_API_KEY`), masked numbers |

## Project layout

```text
app/
  main.py                 FastAPI app, CORS, companion routes, /health
  config.py               environment settings
  db.py                   SQLAlchemy models (Postgres or SQLite); tables created on startup
  security.py             API keys: per-source-system keys + admin key
  facts.py                normalisers (state, class, category, income, mobile ...)
  attribution.py          entry-source attribution, OM/REF codes, link builders, refer-a-friend share links
  companion_api.py        /v1/companion (new web companion) + /v1/jobs/run-reminders
  students.py             Save on WhatsApp, one-time codes (WL-/SAVE-/OK-), My schemes, tracker, reminders
  scheme_view.py          scheme cards / details / summary for the companion (+ optional data/scheme_dates.csv)
  speech/                 TTS / STT provision: provider interface, none/mock/http + vendor placeholders, /v1/speech
  conversation/core.py    channel-agnostic dialogue engine (BotReply)
  conversation/understand.py  rule-based typed-answer understanding ("2nd year BA" -> UG, "8000 a month" -> income)
  conversation/texts.py   English wording + language list; conversation/i18n/<code>.py = 13 other languages
  channels/whatsapp.py    WhatsApp adapter (webhook, Graph API client)
  channels/web.py         web chat adapter (REST)
  integration.py          /v1 integration contract
  results.py              result payloads + signed callbacks
  admin.py                admin HTML page
  eligibility/            Rule V3.0 engine + scheme-master compiler (Product 2's own copy)
  static/companion/       new companion: index.html + styles.css + strings.js + icons.js + app.js (served as one page)
  static/companion/lang/  page labels in Bengali, Marathi, Tamil, Telugu, Kannada (+ State names incl. Hindi), loaded on demand
  static/                 companion.html (previous page, /companion/classic), embed.js, embed_demo.html
data/                     MoSJE_Scholarship_Master_V3.0.xlsx + compiled scheme_rules_v3.json + scheme_dates.csv (last dates, empty)
templates/                referrals_template.csv, scheme_dates_template.csv
tests/                    pytest suite (Graph API mocked)
tools/                    local_chat.py, round_trip_demo.py, compile_master.py, build_docx.py
docs/                     SPEECH_API.md, audits, sample transcripts, screenshots, translations
render.yaml               Render Blueprint (1 free web service + env group; no database)
```

## Try it locally

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                           # 150 tests, SQLite, Graph API mocked
P2_TEST_DATABASE_URL=postgresql://user@localhost/db pytest   # same suite on Postgres
python tools/local_chat.py                       # chat with the bot in the terminal (fake WhatsApp)
python tools/round_trip_demo.py                  # Product 1 -> Product 2 -> Product 1 sample
P2_API_KEY=local PUBLIC_BASE_URL=http://127.0.0.1:8000 uvicorn app.main:app --reload   # open http://127.0.0.1:8000/companion
```

Without `DATABASE_URL`, a local SQLite file `p2_local.db` is used. After replacing the scheme master xlsx, run `python tools/compile_master.py`. Rebuild the Word documents with `python tools/build_docx.py INTEGRATION_SPEC.md` and `python tools/build_docx.py SETUP_GUIDE.md`.

## Environment variables

See `.env.example`. Key ones: `DATABASE_URL`, `P2_API_KEY` (admin), `P2_API_KEYS` (`p1-rajat:key1,p1-teamB:key2`), `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_DISPLAY_NUMBER`, `WHATSAPP_APP_SECRET` (optional), `ALLOWED_ORIGINS`, `COMPANION_PUBLIC`, `PUBLIC_BASE_URL` (defaults to Render's `RENDER_EXTERNAL_URL`).

Update 3 (all optional): `WHATSAPP_WEB_LINK` (`offer` / `off`), `ONE_TIME_LINK_TTL_HOURS` (48), `P2_RANK_STATE_FIRST` (true), `WHATSAPP_REMINDER_TEMPLATE` + `WHATSAPP_REMINDER_TEMPLATE_LANG`, `SPEECH_ENABLED` (false), `SPEECH_PROVIDER` (none), `SPEECH_API_KEY`, `SPEECH_API_URL`, `SPEECH_MAX_CHARS`, `SPEECH_RATE_LIMIT`. One-time links need `PUBLIC_BASE_URL` (on Render it is filled automatically).

## What is stubbed / integration later

| Piece | Today | Needed to finish |
|---|---|---|
| Speech (TTS / STT, WhatsApp voice notes) | Off; web falls back to the phone's own voice, mic shows “coming soon”; voice notes get a “please type” reply | Choose a vendor, set `SPEECH_*` ([docs/SPEECH_API.md](docs/SPEECH_API.md)) |
| Reminders outside WhatsApp's 24-hour window | Planned and stored; sent as free text only if the student wrote in the last 24 h, else marked `NOT_SENT` | A Meta-approved utility template (`WHATSAPP_REMINDER_TEMPLATE`) and a daily call to `POST /v1/jobs/run-reminders` (cron / external scheduler) |
| Scheme last dates / renewal dates | Not in the V3.0 master; cards say “Check portal”; students can add a date in My schemes | Fill `data/scheme_dates.csv` (template in `templates/`) |
| Refer a friend | Works end to end (codes, links, WhatsApp share, `PEER_REFERRAL` tagging, counts) | Rewards / leaderboards, if wanted |
| Feedback | Stored in `p2_feedback` (web + WhatsApp), visible via `GET /v1/companion/feedback` | Dashboard / export, if wanted |
| Page translations | Hindi, Bengali, Marathi, Tamil, Telugu, Kannada page labels + State names, **machine-drafted**; Assamese, Gujarati, Malayalam, Odia, Punjabi page labels in English (chat translated) | Native review (`docs/translations/companion/`), more `lang/<code>.json` packs |

