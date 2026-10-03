"""All bot wording. English is the source; other languages live in app/conversation/i18n/<code>.py.

Rules for translators (see TRANSLATIONS_REVIEW.md):
  * keep {placeholders} and emoji unchanged; keep *asterisks* (WhatsApp bold) around the same words;
  * option / button labels (keys starting o_, g_, cat_, inc_, prefill_, wa_) must be <= 20 characters
    (WhatsApp reply-button limit); tests/test_update1.py enforces this for every language;
  * scheme names, benefits and State names stay in English (they come from the scheme master).
Languages other than English were machine-drafted and need native-speaker review.
"""
from __future__ import annotations

import importlib

# code -> English name, native name. Order = order in the language picker.
LANGS = {
    "en": {"en": "English", "native": "English"},
    "hi": {"en": "Hindi", "native": "हिंदी"},
    "bn": {"en": "Bengali", "native": "বাংলা"},
    "as": {"en": "Assamese", "native": "অসমীয়া"},
    "kn": {"en": "Kannada", "native": "ಕನ್ನಡ"},
    "ta": {"en": "Tamil", "native": "தமிழ்"},
    "te": {"en": "Telugu", "native": "తెలుగు"},
    "ml": {"en": "Malayalam", "native": "മലയാളം"},
    "or": {"en": "Odia", "native": "ଓଡ଼ିଆ"},
    "bho": {"en": "Bhojpuri", "native": "भोजपुरी"},
    "mai": {"en": "Maithili", "native": "मैथिली"},
    "gu": {"en": "Gujarati", "native": "ગુજરાતી"},
    "mr": {"en": "Marathi", "native": "मराठी"},
    "pa": {"en": "Punjabi", "native": "ਪੰਜਾਬੀ"},
}
LANG_CODES = list(LANGS)
# picker order: alphabetical by English name (Update 1, feedback 6)
LANG_ORDER = sorted(LANG_CODES, key=lambda c: LANGS[c]["en"])


def lang_label(code: str) -> str:
    L = LANGS[code]
    return L["en"] if code == "en" else f"{L['native']} ({L['en']})"


EN = {
    # --- welcome / language
    "welcome_named": "Namaste {name}! 👋 I am the MoSJE Scholarship Discovery Assistant.",
    "welcome": "Namaste! 👋 I am the MoSJE Scholarship Discovery Assistant.",
    "intro": "Answer a few quick questions (about 2 minutes) and I will show scholarships you can explore.",
    "choose_lang": "Please choose your language / कृपया भाषा चुनें:",
    "lang_set": "✅ Language: {language}",
    # --- pre-filled facts
    # --- questions
    "q_step": "({n}/{total})",
    "q_class_passed": "What is your current education level?",
    "q_state": "Which state's scholarships would you like to see?",
    "q_category": "What is your social category?",
    "q_gender": "What is your gender?",
    "q_annual_family_income": "Which range best describes your family's total *monthly* income?",
    "current_answer": "(Your current answer: {v})",
    "cls_X": "Class 10 passed", "cls_XII": "Class 12 passed", "cls_PRE": "Class 1–10 (Pre-Matric)",
    "cls_UG": "Graduation (UG)", "cls_PG": "Post Graduation (PG)", "cls_OTHER": "Other / not studying",
    "o_edu_PRE": "Class 1–10 (school)",
    "o_edu_X": "Class 10 passed",
    "o_edu_XII": "Class 12 passed",
    "o_edu_UG": "Graduation (UG)",
    "o_edu_PG": "Post Graduation (PG)",
    "o_edu_OTHER": "Other / not studying",
    "edu_d_PRE": "Studying in school – Pre-Matric",
    "edu_d_X": "Matric – now in Class 11/12 (Post-Matric)",
    "edu_d_XII": "Post-Matric – college, diploma or ITI",
    "edu_d_UG": "Studying for a bachelor's degree",
    "edu_d_PG": "Master's degree, M.Phil or PhD",
    "edu_d_OTHER": "None of the above",
    "o_dont_know": "Don't know",
    "o_skip": "Skip",
    "o_yes": "Yes", "o_no": "No", "o_prefer_not": "Prefer not to say",
    "cat_SC": "SC", "cat_ST": "ST", "cat_OBC": "OBC", "cat_General": "General", "cat_Minority": "Minority",
    "g_Female": "Female", "g_Male": "Male", "g_Transgender": "Transgender",
    "inc_m10k": "Up to ₹10,000",
    "inc_m30k": "₹10,001–₹30,000",
    "inc_gt30k": "Above ₹30,000",
    "per_month": "{v} a month",
    "per_year": "{v} a year",
    # --- consent (wording based on the SETU chatbot consent, Rule Engine v4 'Language Rules - Consent')
    "consent": ("🔒 To find scholarships that may be relevant, I need to use the details you share in this chat "
                "(education level, gender, family income, social category and State). They are used only to "
                "suggest schemes. I will not ask for your name, Aadhaar or bank details. Is that okay?"),
    "o_agree": "Agree",
    "o_disagree": "Don't agree",
    "o_agree_now": "I agree now",
    "consent_declined": ("Understood 🙏 I won't ask for or keep any personal details. You can still explore all "
                         "scholarships on the National Scholarship Portal: https://scholarships.gov.in/\n"
                         "If you change your mind, tap below or reply HI."),
    # --- summary before matching
    "summary_title": "📋 Please check your details:\n{facts}\n\nShall I look for scholarships now?",
    "records_note": "📁 = from your records",
    "o_proceed": "Proceed",
    "o_edit": "Edit details",
    "edit_restart": "OK, let's go through the questions again.",
    # --- fallback / errors
    "fallback": "I didn't get that 🙂 Please tap an option below or type its number. You can also type MENU, BACK or HELP.",
    "nothing_back": "You are at the first step.",
    "updated": "✅ Updated {f}: {v}",
    "class_other": ("Right now I can help students from Class 1 up to Post Graduation. "
                    "You can explore all scholarships at https://scholarships.gov.in/\nReply HI any time to start again."),
    # --- results list
    "summary": "Your answers: {facts}",
    "results_head": "Based on your answers, here are {n} scholarship(s) you can explore (showing {a}–{b} of {total}):",
    "results_head_check_only": ("No scheme matched all your answers for certain. These {n} scheme(s) are only for "
                                "specific groups – check if one applies to you (showing {a}–{b} of {total}):"),
    "results_none": ("I could not find a scheme in our list that matches all your answers. "
                     "You can change your answers or explore https://scholarships.gov.in/"),
    "list_tap": "Tap a scheme (or type its number) to see details.",
    "check_section": "Only for specific groups – check eligibility",
    "only_for": "Only for: {groups}",
    "check_elig": "check eligibility",
    "central": "Central",
    "results_foot": ("ℹ️ This list is based only on your answers and the Scholarship Eligibility Rule V3.0. "
                     "Final eligibility is decided by the scheme's department when you apply."),
    "no_more": "That was the full list.",
    "grp_disability": "students with disabilities",
    "grp_farmer": "farmer families",
    "grp_workers": "children of specific workers",
    "grp_defence": "armed forces / police families",
    "grp_school": "students of specific schools",
    "grp_orphan": "orphans / PM CARES children",
    "grp_bpl": "BPL families",
    "grp_teachers": "children of teachers",
    "grp_other": "a specific group",
    "grp_income": "family income up to {amt} a year",
    # --- detail card
    "d_type": "Type",
    "d_benefit": "Benefit",
    "d_stage": "Education stage",
    "d_category": "Category",
    "d_gender": "Gender",
    "d_income": "Family income",
    "d_income_upto": "up to {amt} a year",
    "d_age": "Age",
    "d_domicile": "State / domicile",
    "d_only_for": "Only for",
    "d_other": "Other conditions",
    "d_deadline": "Last date",
    "d_link": "More info / apply",
    "d_inferred": "from scheme name – please verify",
    "d_description": "Description",
    "d_eligibility": "Eligibility",
    "d_docs_short": "Required documents",
    "d_apply": "Application",
    "see_site": "See official site",
    "more_details": "More details",
    "na": "Not available – check official site",
    "link_unverified": "link not verified – search the scheme name on the official site",
    "guidance": "ℹ️ This is guidance only – verify on the official site before applying.",
    # --- navigation / menu
    "o_more": "More schemes",
    "o_back": "Go back",
    "o_back_list": "Back to list",
    "o_menu": "Main menu",
    "o_find": "Find scholarships",
    "o_my_schemes": "See my schemes",
    "o_lang": "Language",
    "o_help": "Help",
    "o_feedback": "Share feedback",
    "o_share_scheme": "Share scheme",
    "o_view": "View details",
    "menu_title": "🏠 Main menu – what would you like to do?",
    "help": ("I help you find government scholarships in 2 minutes.\n"
             "• Tap an option or type its number.\n"
             "• BACK – previous step · MENU – main menu · HI – start again\n"
             "• LANGUAGE – change language · STOP – stop messages\n"
             "Your answers are used only to suggest schemes. Official portal: https://scholarships.gov.in/"),
    "stopped": "You will not get more messages from us. Reply HI any time to start again.",
    "reply_number": "Reply with a number:",
    # --- why / wrong
    "why": ("Sorry if the list looked wrong 🙏 I only show schemes that match your answers:\n{facts}\n"
            "Schemes marked \"Only for…\" are for specific groups (for example farmer families) – check before applying. "
            "If an answer is wrong, change it below."),
    "why_cat_same": "Your saved category is {cat}, so schemes only for other categories are not shown.",
    "why_cat_diff": "You mentioned {said}, but your saved category is {cat}. Tap below to update it.",
    "why_early": "I show schemes after a few quick questions. Please answer the question, or change your answers any time.",
    # --- feedback / share
    "q_rating": "How would you rate this service? 1 ⭐ = lowest, 5 ⭐ = highest.",
    "r_1": "Very poor", "r_2": "Poor", "r_3": "Okay", "r_4": "Good", "r_5": "Excellent",
    "q_comment": "Thank you! Any comment or suggestion? Type it, or reply SKIP.",
    "share": ("🙏 Thanks for your feedback!\nKnow a student who could use this? Share your personal link:\n"
              "WhatsApp: {wa}\nWeb: {web}\nOr ask them to send the code *{code}* to this number."),
    "share_no_wa": "(WhatsApp link available once the WhatsApp number is set up)",
    "share_scheme_intro": "📤 Forward this message to friends on WhatsApp, email or social media:",
    "share_scheme_msg": ("🎓 I found this scholarship: *{name}* ({tag})\n{desc}\nApply: {url}\n\n"
                         "Find scholarships for you in 2 minutes:\nWhatsApp: {wa}\nWeb: {web}"),
    "share_subject": "A scholarship you may be eligible for",
    "share_fwd_hint": "☝️ Long-press the message above and tap Forward to share it.",
    "sh_whatsapp": "WhatsApp", "sh_email": "Email", "sh_copy": "Copy message", "sh_more": "Share…",
    "sh_copied": "Copied ✓",
    "share_invite": "🎓 I found government scholarships for me in 2 minutes – free, and no documents needed to check. Try it: {link}",   # refer a friend: forwarded message (Update 3)
    "menu_hint": "Type MENU for the main menu.",
    "lang_continue": "Continue",
    # --- labels
    "f_class_passed": "Education level", "f_state": "State/UT", "f_category": "Category", "f_gender": "Gender",
    "f_annual_family_income": "Family income",
    # --- WhatsApp interactive messages
    "wa_choose": "Choose",
    "wa_options": "Options",
    "wa_nav": "Navigate",
    "wa_next": "More options ▶",
    "wa_prev": "◀ Previous",
    "wa_page": "Page {p} of {n} – choose an option:",
    "choose_next": "What would you like to do next?",
    "unsupported": "Please reply with text (a number or a word).",
    # --- Update 3: refer a friend, one-time web link, Save on WhatsApp, voice notes
    'o_refer': 'Refer a friend',
    'refer': '🤝 Know a student who could use this? Share your personal link:\nWhatsApp: {wa}\nWeb: {web}\nOr ask them to send the code *{code}* to this number.',
    'web_link': '📱 Prefer a bigger screen? Open your one-time link (only for you, expires in {h} hours):\n{url}',
    'my_link': '📋 Your saved schemes, reminders and application tracker (one-time link, only for you):\n{url}',
    'save_ok': "✅ Saved! {n} scheme(s) are in My schemes. We'll remind you before last dates. Reply STOP anytime.\n{url}",
    'save_bad': 'This code is not valid or has expired. Please tap Save again on the web page.',
    'parent_ok': "✅ Thank you. Your consent is recorded. Reminders will now go to your child's number.",
    'voice_soon': '🎤 Voice notes are coming soon. Please type your answer for now.',
    'voice_heard': '🎤 I heard: “{text}”',
    'no_saved': 'You have not saved any schemes yet. Find scholarships first, then tap Save on the web page.',
}

T = {"en": EN}
for _code in LANG_CODES[1:]:
    try:
        T[_code] = importlib.import_module(f".i18n.{_code}", __package__).T
    except ModuleNotFoundError:          # pragma: no cover - a language file is missing
        T[_code] = {}

# keys whose values are shown as WhatsApp buttons/list rows (length-limited)
BUTTON_KEYS = [k for k in EN if k.startswith(("o_", "g_", "cat_", "prefill_", "wa_choose"))]
ROW_KEYS = [k for k in EN if k.startswith(("inc_", "f_", "wa_next", "wa_prev", "wa_options", "wa_nav"))]


def t(lang: str, key: str, **kw) -> str:
    s = T.get(lang, EN).get(key) or EN.get(key, key)
    return s.format(**kw) if kw else s
