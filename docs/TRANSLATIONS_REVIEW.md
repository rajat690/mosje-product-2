# Translations – review guide (Product 2, Update 1)

The chat now runs in **14 languages**: Assamese, Bengali, Bhojpuri, English, Gujarati, Hindi, Kannada, Maithili,
Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu (shown in this alphabetical order, by English name, with the native
script first, e.g. "বাংলা (Bengali)").

## Status – please read

* **Web page (`/companion`, Update 3, 2 Oct 2026):** its labels, document help texts and State names have their own files – see [COMPANION_TRANSLATIONS.md](COMPANION_TRANSLATIONS.md) and `docs/translations/companion/`.

* **All non-English texts are machine-drafted and need a native-speaker review before real students use them.**
* Hindi: 25 of the 57 Hindi strings from the original repo are unchanged. The other 134 Hindi strings are new or
  rewritten for Update 1 (consent, the 5 questions, summary, scheme cards, share and star feedback).
* Scheme names and the short scheme fields (Description / Eligibility / Required documents) come from the English
  scheme master, so they stay in English in every language.
* In Hindi and Punjabi the bot speaks about itself with masculine verb forms (e.g. `help`: "मैं … मदद करता हूँ").
  This is grammatical, but a reviewer may prefer neutral wording. Student-facing questions avoid gendered forms.
* The consent text follows SETU's "Language Rules – Consent" wording, expanded a little. The SETU team should confirm it.

## Files

| File | What it is |
|---|---|
| `app/conversation/texts.py` | English master texts (`EN`) and the language list |
| `app/conversation/i18n/<code>.py` | one file per language (`hi`, `bn`, `as`, `kn`, `ta`, `te`, `ml`, `or`, `bho`, `mai`, `gu`, `mr`, `pa`) |
| `docs/translations/translations_review.xlsx` | every key × 14 languages in one sheet, with the character limit for each key – easiest for reviewers |
| `docs/translations/translations_all.csv`, `docs/translations/<code>.csv` | the same as CSV |

## WhatsApp limits (checked by the tests)

* Buttons (`o_*`, `g_*`, `cat_*`, `wa_choose`): **max 20 characters**. Longer labels are cut by WhatsApp.
* List rows (`inc_*`, `f_*`, `wa_next`, `wa_prev`, `wa_options`, `wa_nav`): **max 24 characters**.
* Keep every `{placeholder}` exactly as it is (e.g. `{name}`, `{n}`, `{url}`).
* Keep `HI`, `MENU`, `BACK`, `HELP`, `SKIP`, `STOP` in Latin letters. Students can type these keywords in any language.

## How to change a translation

1. Open `app/conversation/i18n/<code>.py` (or edit the spreadsheet and send it to the developer).
2. Change the text between the quotes. Do not change the key on the left.
3. Run the tests: `python -m pytest -q`. `test_all_languages_complete_and_button_limits` fails if a key is missing,
   a placeholder differs or a label is too long.
4. Optional: `python tools/local_chat.py --sep "|" --script "hi|<language number>|1|..."` shows the conversation
   in the terminal.
5. Upload the changed file to GitHub. Render deploys it automatically, or use Manual Deploy.
6. Run `python tools/export_translations.py` to refresh the spreadsheet.
