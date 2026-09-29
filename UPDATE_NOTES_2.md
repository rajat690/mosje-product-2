# Product 2 – Update 2 (29 Sep 2026)

Small changes to the question order and screens after your test of Update 1. They apply to the web companion and to WhatsApp, in all 14 languages.

## 1. What changed for the student

| # | Change | What the bot does now |
|---|---|---|
| 1 | State first | After language and consent, the questions are: **(1/5) State/UT** (“Which state's scholarships would you like to see?”) → (2/5) education level → (3/5) gender → (4/5) family income → (5/5) social category → summary. The summary also lists State first. **Edit details** goes back to question 1 (State) and keeps the language and consent. Choosing “Other / not studying” for education still ends the chat politely. |
| 2 | Summary buttons | Only **Proceed** and **Edit details** (no Main menu). |
| 3 | Short scheme list | Each scheme in the list shows only its number and name, the State/Central tag, the department, and a **View details** button. Description, eligibility, documents, application link and “More details” are shown only when the student opens the scheme. On WhatsApp the list is short too: *name · State/Central · Department*. |
| 4 | Detail buttons | **Go back / Share scheme / Share feedback** only (no Main menu). On WhatsApp these are 3 buttons, with the line “Type MENU for the main menu.” below the details. Main menu has also been removed from the results list, share and feedback steps. On the web, the **Menu** and **Restart** buttons at the top stay. |

Screenshots (web companion): `docs/screenshots/update2_01_question1_state.png`, `update2_02_summary_no_menu.png`, `update2_03_compact_listing.png`, `update2_04_detail_3_ctas.png`, `update2_05_hindi_listing.png`.
Sample WhatsApp chats: `docs/sample_update2_whatsapp_transcript.md` (English) and `docs/sample_update2_bengali_transcript.md` (Bengali).

## 2. How to upload (no coding needed)

1. Unzip `mosje_product2_update2.zip`. It contains **only the files changed since Update 1**, in their folders, plus `UPDATE2_FILE_LIST.txt` (the list of files).
2. On GitHub, open **rajat690/mosje-product-2** → **Add file → Upload files**. Drag in the **folders** (`app`, `docs`, `tests`, `tools`) and the top-level files, so the folder structure is kept. Existing files are replaced. (Do not drag files one by one into the top level.)
3. Write a commit message, for example “Update 2 – State first, shorter list, fewer buttons”, and press **Commit changes**.
4. In Render, open **mosje-p2-api** → **Manual Deploy** → **Deploy latest commit**. Wait until it shows *Live* (a few minutes).

**Database changes:** none. **Environment variables:** none to add or change. No files need to be deleted.

## 3. Quick test after deploy

* Web: open `https://mosje-p2-api.onrender.com/companion` → English → Agree. The first question should be “(1/5) Which state's scholarships would you like to see?”. Type `Rajasthan`, then Class 10 passed → Female → Up to ₹10,000 → SC. The summary starts with State and has only Proceed / Edit details. Proceed → the short list → View details → Go back / Share scheme / Share feedback.
* WhatsApp: send `hi` to the test number and repeat. The detail message has 3 buttons and “Type MENU for the main menu.”

## 4. Notes

* The State answer is still used as the student's home State for the eligibility check (Rule V3.0 “Jurisdiction”), exactly as before. Only the wording and position of the question changed.
* The new State question was translated automatically into the 13 other languages. Please ask native speakers to check it (`docs/translations/`).
* The consent message still lists the details in the old order (“education level, gender, family income, social category and State”). The meaning is the same, and it can be reordered later if you want.
* In the list, schemes that are only for specific groups still appear under the heading “Only for specific groups – check eligibility”. The exact group (for example “farmer families”) is now shown only in the detail view (“More details”).
* Main menu is still available by typing MENU (WhatsApp) or with the Menu button at the top (web). The 5 questions still have Go back / Main menu.
* Automated tests: 101 passed on SQLite and 101 passed on PostgreSQL.
