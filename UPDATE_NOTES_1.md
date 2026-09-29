# Product 2 – Update 1 (29 Sep 2026)

This update fixes the category bug from the live test and redesigns the chat around your feedback items 1–11.
It works on WhatsApp and on the web companion.

## 1. What changed for the student

| # | Feedback | What the bot does now |
|---|---|---|
| 1 | General student saw SC/OBC schemes | Scheme categories, gender and target groups are filled in where the master says “Not specified” (from the scheme name or department). The Karnataka Class 10 General boy from the live test now gets **no** reserved-category schemes. 3 group-only schemes (farmer families, students with disabilities, PM CARES children) appear only under “check eligibility”. Free-text complaints (“why are you showing me SC schemes?”) get a friendly explanation instead of “I didn't get that”. Full list: `docs/CATEGORY_AUDIT.md`. |
| 2 | List + detail cards | List of scheme cards; tap **View details** for the full card. |
| 3 | Navigation | **Go back** and **Main menu** at every step (within WhatsApp's button limits). |
| 4 | Languages | 14 languages: Assamese, Bengali, Bhojpuri, English, Gujarati, Hindi, Kannada, Maithili, Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu. |
| 5 | Max 5 questions | (1) Education level: Class 1–10 / Class 10 passed / Class 12 passed / Graduation (UG) / Post Graduation (PG) / Other; (2) Gender: Male / Female; (3) Family income: SETU bands; (4) Social category: SETU options; (5) State/UT. The disability question is removed. Disability, farmer and other group schemes are shown as “check eligibility”. |
| 6 | Language first | Web: alphabetical dropdown (native script + English name) with **Continue**. WhatsApp: alphabetical list (2 pages; English is no. 4). |
| 7 | Consent | Right after language: short consent text with **Agree / Don't agree**. The decision and time are saved. If the student does not agree, the bot ends politely and keeps nothing personal: answers and pre-filled facts are deleted and later messages are not stored. |
| 8 | Summary | After the 5 questions: summary with **Proceed / Edit details**. *Edit details* restarts at the education question and keeps language and consent. |
| 9 | Card format | **Scheme name · State/Central · Department**, then Description (≤40 characters), Eligibility (≤50), Required documents (≤40) and the application link. These are prepared from the master when the rules are built. Missing values show “See official site”. |
| 10 | After details | **Go back / Share scheme / Share feedback**. *Share scheme* = a ready-made message with the student's personal referral links (WhatsApp `wa.me` + web). On WhatsApp it is sent on its own so it can be forwarded. On the web there are WhatsApp, Email, Copy message and Share (phone share sheet) buttons. |
| 11 | Feedback | 1–5 stars (WhatsApp: a list with ⭐ labels; web: star buttons), then an optional comment. |

Screenshots: `docs/screenshots/update1_01…14_*.png`. These cover the language dropdown, consent, a question, summary, list cards, detail card and “More details”, share, stars, the Karnataka General fix, the “why” answer, consent declined, and Bengali and Hindi screens.
Sample chats: `docs/sample_update1_whatsapp_transcript.md`, `docs/sample_update1_bengali_transcript.md`.

### Options copied from SETU (please confirm with the SETU team)

These were taken from `SETU_FreeText_Rule_Engine_v4.docx` (and the SETU handover notes) in the workspace:

* **Family income**: SETU asks *monthly* household income: **Up to ₹10,000 / ₹10,001–₹30,000 / Above ₹30,000**. SETU v4 has no “Prefer not to say”, so none is offered here. The scheme master uses *yearly* ceilings, so the bands are converted to yearly amounts: up to ₹1.2 lakh, ₹1.2–3.6 lakh, above ₹3.6 lakh. If a scheme's ceiling falls inside the student's band (for example ₹2.5 lakh for the middle band), the scheme is shown under “check eligibility” with the ceiling.
* **Social category**: **SC / ST / OBC / General / Minority** (same as SETU).
* **Consent**: SETU's wording (“To find schemes that may be relevant, I need to use the details you share in this chat. Is that okay?”), expanded to list the 5 details and to say that name, Aadhaar and bank details are never asked. The buttons are *Agree / Don't agree* as you asked (SETU uses Yes / No).
* **Gender**: Male / Female only, as you asked. SETU and the master also know Transgender. Please reconsider adding it back. A Product 1 referral can still send it.

## 2. How to upload (no coding needed)

1. Unzip `mosje_product2_update1.zip`. It contains **only the new and changed files**, in their folders, plus `UPDATE1_FILE_LIST.txt`.
2. On GitHub, open **rajat690/mosje-product-2** → **Add file → Upload files**. Drag in the **folders** (`app`, `data`, `docs`, `tests`, `tools`) and the top-level files, so the folder structure is kept. Existing files are replaced.
   *Tip:* dragging the folders from the unzipped update keeps the paths. Do not drag the files one by one into the top level.
3. Write a commit message, for example “Update 1 – consent, 5 questions, cards, share, stars”, and press **Commit changes**.
4. Render usually deploys automatically. If not:
   * Render → **Blueprints** → your blueprint → **Manual sync**, **or**
   * Render → **mosje-p2-api** → **Manual Deploy** → **Deploy latest commit**.
5. Wait for “Live” (about 2–4 minutes), then open `<service URL>/health`. It should show `"status":"ok"` and `"schemes_active":525`.

(Alternatively upload the full `mosje_product2.zip` contents. Both give the same result.)

## 3. Settings and database

* **Environment variables: nothing new is required.** Optional: `WHATSAPP_INTERACTIVE` (default `true`; set `false` only if WhatsApp buttons/lists cause problems, and the bot then sends numbered text).
* **Database: no manual steps, no data loss.** At start-up the app adds the 3 new consent columns (`consent_status`, `consent_at`, `consent_version`) to the Neon database automatically, plus any other column an older database is missing. They are nullable "add column" changes, so existing sessions, referrals and results stay as they are.

## 4. Quick test after the deploy

1. **Web:** open `<service URL>/companion` → pick **English** in the dropdown → **Continue** → **Agree** → Class 10 passed → Female → Up to ₹10,000 → SC → type `Rajasthan` → **Proceed**. You should see cards with Description / Eligibility / Required documents / Application. Tap **View details** → **Share scheme** (WhatsApp / Email / Copy buttons) → **Share feedback** (stars).
2. **Karnataka check:** Restart → English → Agree → Class 10 passed → Male → Above ₹30,000 → General → `Karnataka` → Proceed. There should be no Backward Classes / SC / OBC schemes, only 3 “check eligibility” cards.
3. **WhatsApp (test number):** send `hi` → language list → English → Agree → answer 5 questions → Proceed → tap a scheme → buttons **Go back / Share scheme / Share feedback**.
4. **Consent declined:** Restart → English → **Don't agree**. You get a polite goodbye with scholarships.gov.in. `GET /v1/results` shows `status: CONSENT_DECLINED` with no answers.

## 5. For Product 1 teams (API changes, all backward compatible)

* `class_passed` now also accepts `PRE`, `UG`, `PG` (plus `X`, `XII` as before).
* The result object has a new `consent` block (`status`, `at`, `version`), new answers `income_min` / `income_band`, and a new status `CONSENT_DECLINED` (session and referral).
* Chat replies carry `cards[].title_line/description/eligibility/documents/url/department`, `detail.short`, `share.message/whatsapp_share_url/email_url` and `ui` (language dropdown).
* Details are in `INTEGRATION_SPEC.md` / `.docx`, sections 4, 6.1, 8, 9 and 12.

## 6. Points to confirm / known limits

* **SETU options** (income bands, categories, consent text) should be confirmed with the SETU team (see above).
* **Education levels UG/PG and Class 1–10** extend Rule V3.0, which only derives Pre-/Post-Matric from Class 10/12. The master's education text is mapped to levels for 49 schemes (PG-only 19, Class XI–XII 18, and so on). This is a product decision to confirm.
* **Master data is thin:** only 45 of 525 active schemes have Benefits / Documents text. Other descriptions come from the programme type (“Scholarship” for 236 schemes). Documents show “See official site” for 480 schemes, and 45 have no department. The master's own benefit text is already cut at about 150 characters. There is no deadline column, so “Last date” is always “Not available”. Filling the master improves the cards automatically (`python tools/compile_master.py`). Counts: `docs/CATEGORY_AUDIT.md` → “Short display fields”.
* **Inferred categories and groups** (from names/departments) are marked in `docs/category_audit.csv`. 15 rows (mostly department-based inferences) are marked `Needs_Review=YES`.
* **Translations** in all 13 non-English languages are machine-drafted and need native-speaker review. See `docs/TRANSLATIONS_REVIEW.md` and `docs/translations/translations_review.xlsx`.
* **Transgender** option removed from the chat as instructed (recommend reconsidering).
* Everything is still for **synthetic/test data only** on Render/Neon.

## 7. Tests

93 automated tests pass on SQLite and on PostgreSQL (`python -m pytest -q`). New tests cover the language order, consent (agree, decline with nothing stored, referral marked), the 5-question order, summary Proceed / Edit details, income bands (including “check eligibility” for ceilings inside a band), education levels, short-field limits for every scheme, the card and detail format, share links, WhatsApp forwardable share message, 3-button detail with typed MENU, star feedback, all 14 languages and WhatsApp payload limits in every language.
