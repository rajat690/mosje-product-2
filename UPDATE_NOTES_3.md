# Product 2 – Update 3 (2 Oct 2026)

Built from **Product Vision V1.0** (2 Oct 2026) and the chosen mobile prototype (“MoSJE WhatsApp Companion Prototype”). It also includes the **scheme data audit** of 29 Sep (`docs/SCHEME_DATA_AUDIT.md`), which was prepared but not yet on GitHub.

## 1. What changed for the student

| # | Change | What happens now |
|---|---|---|
| 1 | New web companion (`/companion`) | A mobile-first page that looks and feels like a WhatsApp chat, with big tap targets, one scroll and a “Waking up the server…” note on a cold start. The language list shows each language in its own script, followed by a one-line consent. The **5 questions** follow, and the State question offers the 6 most likely States plus type-ahead. **Typed answers are understood**: “I am in 2nd year BA” gives “You mean Graduation (UG)?” with Yes / No, and “8000 per month” is read as the family income. A **review card** then shows **Edit** next to each answer. The page is about 140 KB (each extra language adds a ~30 KB pack, loaded only when chosen). The previous page is still at `/companion/classic`. |
| 2 | Results | Your own State's schemes come first, then the best matches. The summary shows the number of scholarships, **“Up to ₹X a year”** (X = the biggest single yearly amount among the eligible schemes – amounts are **not added together**, because a student usually gets one scholarship at a time), the eligible count and the to-check count, with filter chips (All / Eligible / To check / Closing soon). Each card shows the amount, the last date (“Check portal” until dates are added), at most one thing to check with Yes / No / Not sure, the number of documents and a ☆ Save. “Applying is free. Never pay anyone.” is shown. |
| 3 | Scheme details | **Why you match**, **one thing to check**, a **documents checklist** in plain words with “How to get it” (Aadhaar: “you'll need it when you apply”), **3-step How to apply**, **Listen**, **Share with parent**, **Save** and **Apply on official site**. |
| 4 | Save on WhatsApp | Journeys 1 and 2 (the page was opened from the WhatsApp one-time link): one tap. Journey 3 (anonymous web): the student enters a number, then sends “Hi, please save my scholarships. Code SAVE-XXXXX” from WhatsApp. This proves the number, with no OTP. Under 18: the parent sends “YES … Code OK-XXXXX” from their WhatsApp before anything is stored. Consent: “We'll keep your number, your answers and saved schemes to send reminders. Reply STOP anytime.” |
| 5 | My schemes | Application tracker (Saved → Documents → Applied → Result → Approved / Rejected, one tap), reminder switches (last date, new schemes, renewal), **Add last date** per scheme, renewal date after Approved, the upcoming WhatsApp reminders list, Refer a friend, Give feedback and **Delete my data**. On WhatsApp, `MY SCHEMES` sends a one-time link straight to this page. |
| 6 | Reminders | Last date: 7 and 2 days before, skipped once Applied. A documents nudge 7 days after “Documents pending”. A result check 30 days after Applied. Renewal: 30 days before the renewal date, with “Are you now in the next class or year? Reply EDIT”. New-scheme alerts: saved answers are re-run, and only new matches are announced. If the student answers again, the saved answers are updated. **Sending outside WhatsApp's 24-hour window needs an approved template (integration later)**. See 4. |
| 7 | Feedback | Web: 5 faces (Very hard … Very easy), optional comment, and the screen / scheme context are stored. WhatsApp: `FEEDBACK` (or Share feedback) → 1–5 → comment / SKIP, as before. Everything goes to the new table `p2_feedback`. Partners see it at `GET /v1/companion/feedback`. |
| 8 | Refer a friend | After feedback, in My schemes and in the menu (web), and with `REFER` or the menu option (WhatsApp). It shows the personal code `REF-XXXXXX`, a message preview, **Send on WhatsApp** (the phone's WhatsApp share screen) and Copy link. Friends who use the link or code are tagged `PEER_REFERRAL`. The web link is `/companion?src=referral&ref=REF-XXXXXX`. |
| 9 | One-time web link on WhatsApp | After the student picks a language on WhatsApp, the bot adds “📱 Prefer a bigger screen? Open your one-time link …”. The link works once, for 48 hours, and only for that number. A forwarded link opens an anonymous page only. |
| 10 | Speech (provision) | The **Listen** button uses the phone's own voice for now, the mic shows “Voice typing is coming soon”, and WhatsApp voice notes get “Voice notes are coming soon. Please type your answer for now.” The server side (`/v1/speech/tts`, `/v1/speech/stt`, voice-note hook) is ready but **switched off** until a vendor is chosen. See `docs/SPEECH_API.md`. |
| 12 | Page in 7 languages (2 Oct) | The whole `/companion` page – buttons, labels, chips, summary, details, documents help, Save, My schemes, tracker, reminders, feedback, refer, menu and error messages – is in **English, Hindi, Bengali, Marathi, Tamil, Telugu and Kannada**. Bhojpuri and Maithili use the Hindi page labels. The questions and answers in the chat were already translated in all 14 languages. **State names** are shown in the student's script (also in type-ahead: typing “தமி” finds தமிழ்நாடு), and a State typed in an Indian script is understood on the web and on WhatsApp. Month names are translated; numbers stay 0–9. Scheme names and details stay in English (as on the official portal) and the page says so. The header language switch lists every language in its own script. The refer-a-friend message is sent in the student's language. **All new translations are machine-drafted and need native review** (see 4). |
| 13 | Amount wording fixes (2 Oct) | “Up to ₹15 lakh total overseas study assistance” is now shown as “₹15,00,000 in total” (not “a year”), “One-time merit award of ₹10,000” as one-time, and “₹5,000–₹20,000” as up to ₹20,000 (it was added up before). Only yearly amounts are used for “Up to ₹X a year”. |
| 11 | Scheme data audit (29 Sep) | The rules file was rebuilt with education-level filtering (for example, no AICTE Diploma schemes for UG, and no PM YASASVI for SC), plus category and gender fixes. Card text limits are 80 / 80 / 90 characters, and the consent-declined message links scholarships.gov.in. See `docs/SCHEME_DATA_AUDIT.md`. |

Screenshots: `docs/screenshots/update3_01_typed_answer.png` … `update3_11_mic_speech_off.png`.

## 2. How to upload (no coding needed)

1. Unzip `mosje-product-2-update3.zip`. It holds the **complete repository** (185 files) in the same folders as GitHub. `UPDATE3_FILE_LIST.txt` lists the 112 files that are new or changed compared with GitHub today.
2. On GitHub, open **rajat690/mosje-product-2** → **Add file → Upload files**. Drag in **everything inside** the unzipped folder: the folders `app`, `data`, `docs`, `templates`, `tests` and `tools`, plus the top-level files (including `.env.example`, which may be hidden on a Mac or PC; turn on “show hidden files”). Existing files are replaced, and nothing needs to be deleted.
3. Commit message, for example “Update 3 – mobile companion, Save on WhatsApp, feedback, refer a friend” → **Commit changes**.
4. Render → **mosje-p2-api** → **Manual Deploy → Deploy latest commit**. Wait for *Live*.
5. `render.yaml` changed (new optional settings). In Render → **Blueprints** → your blueprint → **Sync** (or add the settings by hand). Render asks for values only for the new secret entries (`WHATSAPP_REMINDER_TEMPLATE`, `SPEECH_PROVIDER`, `SPEECH_API_KEY`, `SPEECH_API_URL`), which you can leave **empty**.

**Database:** new tables (`p2_students`, `p2_saved_schemes`, `p2_link_codes`, `p2_reminders`, `p2_feedback`, `p2_share_events`, `p2_events`) and 2 new columns on `p2_sessions` are created automatically at start-up. Existing data is kept. Tested on SQLite and PostgreSQL.

**Environment variables:** none are required. Optional ones are in the table below and in `SETUP_GUIDE.md` (“Update 3 – new settings”).

| Key | Default | Purpose |
|---|---|---|
| `WHATSAPP_WEB_LINK` | `offer` | `offer`: send the one-time web link after the language choice on WhatsApp. `off`: never send it. |
| `ONE_TIME_LINK_TTL_HOURS` | `48` | Validity of one-time links and SAVE / OK codes |
| `P2_RANK_STATE_FIRST` | `true` | Own State's schemes first |
| `WHATSAPP_REMINDER_TEMPLATE`, `WHATSAPP_REMINDER_TEMPLATE_LANG` | empty, `en` | Approved utility template for reminders outside the 24-hour window |
| `SPEECH_ENABLED` | `false` | Speech on/off |
| `SPEECH_PROVIDER`, `SPEECH_API_KEY`, `SPEECH_API_URL` | `none`, empty, empty | Speech vendor (integration later) |
| `SPEECH_MAX_CHARS`, `SPEECH_RATE_LIMIT` | `1500`, `40` | Speech limits |

`PUBLIC_BASE_URL` (used in the one-time links) is filled automatically on Render.

## 3. Quick test after deploy

* Web, on a phone: `https://mosje-p2-api.onrender.com/companion` → English → Agree → type `Raj` → Rajasthan → type `2nd year BA` → Yes → Male → Up to ₹10,000 → SC → Show my scholarships → open a card → Save on WhatsApp → 18 or above → a verified test number → tick → Next → Open WhatsApp & send Hi → send. The page moves to “Saved” and then My schemes.
* WhatsApp: send `hi` → pick a language. The reply should include the one-time link. Open it, finish the questions, and Save should be a single tap. Type `MY SCHEMES`, `REFER` and `FEEDBACK` to try those.
* `/docs` → **POST /v1/jobs/run-reminders** with `{"dry_run": true}` shows what reminders would go out today.

## 4. Needs your decision / integration later

* **29 Sep fixes – decided: keep.** GitHub's latest commit (9ed1d1b, 29 Sep, 10:48 PM IST) had undone them; this update brings back the 80/80/90 card limits, the scholarships.gov.in link in the consent-declined message and the data audit, as you confirmed.
* **Reminder delivery:** WhatsApp only allows free messages within 24 hours of the student's last message. For other reminders you need a Meta-approved *utility* template (name it in `WHATSAPP_REMINDER_TEMPLATE`; each message is charged) and a **daily trigger** for `POST /v1/jobs/run-reminders`. The free Render plan has no cron, so use an external scheduler or a paid Render Cron Job. Until then reminders are stored and marked `NOT_SENT`. Reminder texts are in English for now.
* **Last dates:** the V3.0 master has no last-date, renewal or “last verified” fields. Fill `data/scheme_dates.csv` (template in `templates/`). Until then, students add dates themselves.
* **Speech vendor:** Bhashini, Google, ElevenLabs or Sarvam. All are placeholders, and the `http` gateway option is ready.
* **Translations – need native review before public launch.** All non-English text was **machine-drafted**: the WhatsApp texts (14 languages, `docs/translations/<code>.csv`) and the new web page labels for Hindi, Bengali, Marathi, Tamil, Telugu and Kannada plus State names (`docs/translations/companion/<code>.csv`, see `docs/COMPANION_TRANSLATIONS.md`). A reviewer fills the *reviewer* columns; `python tools/companion_translations.py import <code> <file>` puts the corrections back.
* **Page labels not yet translated:** Assamese, Gujarati, Malayalam, Odia and Punjabi show the page labels in English (their chat questions are translated). Adding one = one more `app/static/companion/lang/<code>.json` (about 360 lines), no code change. On WhatsApp, State names in the State list stay in English (WhatsApp list limits); typed State names in Indian scripts are understood.
* **Under 18:** the parent's number is verified (they send the OK code). The child's own number is not, because it is only used for reminders after the parent agrees.
* **Not built yet (Vision sections 10–11):** assisted / helper mode, parent summary view beyond “Share with parent”, FAQ and callback for NSP errors, “Did you receive the money?” outcome survey and success stories, automatic deletion of inactive profiles (Delete my data is built), the district dashboard (only the API `GET /v1/companion/funnel` exists), A/B testing of outreach templates, and keeping the server warm (paid plan).

## 5. Tests

150 automated tests pass on SQLite and on PostgreSQL. A headless-Chrome walk-through at 390×844 of the main journey (language → consent → typed answers → review → summary → details → Save via SAVE code → My schemes → tracker → last date → feedback → refer → Hindi), plus the one-time WhatsApp link with one-tap Save and the reused-link and mic-off cases, showed no console errors. A second walk-through repeats the whole journey (consent → State typed in the language's script → questions → review → summary → details + documents help → Save on WhatsApp → My schemes → feedback → refer → menu → language switch) in **each of the 7 languages**, with an automatic check for text that is cut off or wider than the 390 px screen: none found (only the intended “…” on long header titles). No console errors. Screenshots: `docs/screenshots/update3_lang_<code>_summary.png` and the full set in the delivery folder.
