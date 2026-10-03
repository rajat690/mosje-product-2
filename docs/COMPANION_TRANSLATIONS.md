# Web companion (`/companion`) – page languages (Update 3, 2 Oct 2026)

> ⚠️ **MACHINE-DRAFTED – NEEDS NATIVE-SPEAKER REVIEW.** Every non-English text on the web page (Hindi, Bengali,
> Marathi, Tamil, Telugu, Kannada) and every translated State name was drafted by machine on 2 Oct 2026. It has
> **not** been checked by a native speaker. Please have each language reviewed before real students use it.

## What is translated

| Language | Page labels, buttons, errors | Document help (“How to get it”) | Month names | State names | Chat questions / answers |
|---|---|---|---|---|---|
| English | ✓ (source) | ✓ | ✓ | ✓ | ✓ |
| Hindi – हिंदी | ✓ | ✓ | ✓ | ✓ | ✓ |
| Bengali – বাংলা | ✓ | ✓ | ✓ | ✓ | ✓ |
| Marathi – मराठी | ✓ | ✓ | ✓ | ✓ | ✓ |
| Tamil – தமிழ் | ✓ | ✓ | ✓ | ✓ | ✓ |
| Telugu – తెలుగు | ✓ | ✓ | ✓ | ✓ | ✓ |
| Kannada – ಕನ್ನಡ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Bhojpuri, Maithili | Hindi labels | Hindi | Hindi | Hindi | ✓ (own language) |
| Assamese, Gujarati, Malayalam, Odia, Punjabi | English labels (not yet) | English | English | English | ✓ (own language) |

Always in English (in every language): scheme names, benefit text and rule details (they come from the official
scheme master; the page shows a one-line note saying so), portal web addresses, codes such as `SAVE-…`, `REF-…`,
and words students know in English: WhatsApp, OTP, SMS, STOP, Hi, SC/ST/OBC, UG/PG, ITI, UDID, CSC, BPL, PM CARES.
Numbers are written 0–9 everywhere (amounts, dates, counts), to match amounts and dates from the data.

Terms follow the existing WhatsApp translations (`app/conversation/i18n/<code>.py`) – for example *scheme* = প্রকল্প /
योजना / திட்டம் / పథకం / ಯೋಜನೆ, *My schemes* = আমার প্রকল্প / माझ्या योजना / என் திட்டங்கள் / నా పథకాలు / ನನ್ನ ಯೋಜನೆಗಳು.

## Where the texts live

| File | Contents |
|---|---|
| `app/static/companion/strings.js` | English + Hindi page labels (built into the page) |
| `app/static/companion/app.js` → `DOCS` | English + Hindi document help texts |
| `app/static/companion/lang/<code>.json` | One pack per language: `strings` (same keys as strings.js), `docs`, `months`, `states`. Loaded only when the student picks that language (~30 KB). `hi.json` holds only the Hindi State names. |
| `app/conversation/i18n/<code>.py` | WhatsApp / chat texts (questions, answers, refer-a-friend message `share_invite`) |
| `docs/translations/companion/<code>.csv` | **Review files** for the web page (one row per text) |
| `docs/translations/<code>.csv` | Review files for the WhatsApp / chat texts |

## How to review (no coding)

1. Open `docs/translations/companion/<code>.csv` in Excel or Google Sheets. Columns: section, key, english,
   hindi_reference, translation, reviewer_ok (Y/N), reviewer_suggestion, notes.
2. For each row, put **Y** in *reviewer_ok*, or write a better text in *reviewer_suggestion*.
   Keep anything in curly brackets exactly as it is (`{n}`, `{x}`, `{d}` …) – the page fills these in.
   Keep it short: buttons and chips must fit on a 360-pixel-wide phone.
3. Send the file back. A developer runs
   `python tools/companion_translations.py import <code> docs/translations/companion/<code>.csv`
   (suggestions replace the draft; rows with changed `{…}` are skipped and listed), then `pytest`, then uploads.
4. To regenerate the review files after changes: `python tools/companion_translations.py export`.

## Adding another language (e.g. Gujarati)

Copy `lang/ta.json` to `lang/gu.json`, translate the values (keep the keys and `{…}`), add the State names, and run
`pytest` (`tests/test_update3_languages.py` checks keys, placeholders and States once the code is added to `FULL`).
No other code change is needed: the page loads `/companion/lang/gu.json` automatically when Gujarati is chosen.

## Checks done on 2 Oct 2026

* Automated: every pack has every key, the same `{placeholders}` as English, all 36 States/UTs, 12 months, and no
  Indian-script digits (tests/test_update3_languages.py).
* Headless Chrome at 390 × 844 for each of the 7 languages: consent → State typed in the language's script →
  questions → review → summary → details + document help → Save on WhatsApp → My schemes → feedback → refer → menu.
  No text cut off or wider than the screen (only the intended “…” on long header titles), no console errors.
  Fonts: the page uses the phone's own Noto fonts (Android) / Nirmala UI (Windows) / system fonts (iPhone) – no
  font download.
