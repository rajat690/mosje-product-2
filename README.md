# MoSJE Product 2 – Scholarship Discovery Assistant

WhatsApp + web chat companion that helps students (Class 10 / 12 pass-outs) discover government scholarships using **Scholarship Eligibility Rule V3.0** and the **547-row MoSJE Scholarship Master V3.0**.

* **Standalone.** It does not import or depend on Product 1. Product 1 systems (for example `p1-rajat`, `p1-teamB`) connect through the versioned **integration contract** in [INTEGRATION_SPEC.md](INTEGRATION_SPEC.md).
* **Channel-agnostic conversation engine** (`app/conversation/`), with adapters for **WhatsApp** (Meta Cloud API) and the **web** (REST chat API + embeddable `/companion` widget).
* **Own eligibility engine** (`app/eligibility/`): the V3.0 checks, copied from the Product 1 reference code, with the scheme master shipped as data (`data/`).
* **Entry-source attribution** on every session: `OUTREACH` (registered outreach message links), `ORGANIC`, `PEER_REFERRAL` (share codes after feedback).
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
| `GET /companion`, `/companion/embed.js`, `/companion/demo` | Chat widget, embed snippet, demo host page |
| `GET /admin` | Admin page (HTTP Basic, password = `P2_API_KEY`), masked numbers |

## Project layout

```text
app/
  main.py                 FastAPI app, CORS, companion routes, /health
  config.py               environment settings
  db.py                   SQLAlchemy models (Postgres or SQLite); tables created on startup
  security.py             API keys: per-source-system keys + admin key
  facts.py                normalisers (state, class, category, income, mobile ...)
  attribution.py          entry-source attribution, OM/REF codes, link builders
  conversation/core.py    channel-agnostic dialogue engine (BotReply)
  conversation/texts.py   English + Hindi wording
  channels/whatsapp.py    WhatsApp adapter (webhook, Graph API client)
  channels/web.py         web chat adapter (REST)
  integration.py          /v1 integration contract
  results.py              result payloads + signed callbacks
  admin.py                admin HTML page
  eligibility/            Rule V3.0 engine + scheme-master compiler (Product 2's own copy)
  static/                 companion.html, embed.js, embed_demo.html
data/                     MoSJE_Scholarship_Master_V3.0.xlsx + compiled scheme_rules_v3.json
templates/                referrals_template.csv
tests/                    pytest suite (Graph API mocked)
tools/                    local_chat.py, round_trip_demo.py, compile_master.py, build_docx.py
docs/                     sample transcript, sample round trip, screenshots
render.yaml               Render Blueprint (1 free web service + env group; no database)
```

## Try it locally

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                           # 51 tests, SQLite, Graph API mocked
P2_TEST_DATABASE_URL=postgresql://user@localhost/db pytest   # same suite on Postgres
python tools/local_chat.py                       # chat with the bot in the terminal (fake WhatsApp)
python tools/round_trip_demo.py                  # Product 1 -> Product 2 -> Product 1 sample
P2_API_KEY=local uvicorn app.main:app --reload   # then open http://127.0.0.1:8000/companion
```

Without `DATABASE_URL`, a local SQLite file `p2_local.db` is used. After replacing the scheme master xlsx, run `python tools/compile_master.py`. Rebuild the Word documents with `python tools/build_docx.py INTEGRATION_SPEC.md` and `python tools/build_docx.py SETUP_GUIDE.md`.

## Environment variables

See `.env.example`. Key ones: `DATABASE_URL`, `P2_API_KEY` (admin), `P2_API_KEYS` (`p1-rajat:key1,p1-teamB:key2`), `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_DISPLAY_NUMBER`, `WHATSAPP_APP_SECRET` (optional), `ALLOWED_ORIGINS`, `COMPANION_PUBLIC`, `PUBLIC_BASE_URL` (defaults to Render's `RENDER_EXTERNAL_URL`).
