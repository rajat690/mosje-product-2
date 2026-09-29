"""All bot wording, English + Hindi. Keep messages short: WhatsApp and a small web widget."""

T = {
    "en": {
        "welcome_named": "Namaste {name}! 👋 I am the MoSJE Scholarship Discovery Assistant.",
        "welcome": "Namaste! 👋 I am the MoSJE Scholarship Discovery Assistant.",
        "intro": "Answer a few quick questions (about 2 minutes) and I will show scholarships you can explore.",
        "choose_lang": "Please choose your language / कृपया भाषा चुनें:",
        "prefill": "From your records we already have:\n{facts}\nIs this correct?",
        "prefill_yes": "Yes, correct",
        "prefill_no": "No, let me answer",
        "q_class_passed": "Which class did you pass most recently?",
        "q_state": "Which State/UT are you a resident (domicile) of? Reply with the number or type the name.",
        "q_category": "What is your social category?",
        "q_gender": "What is your gender?",
        "q_annual_family_income": "What is your family's total annual income? Pick a range or type the amount (e.g. 180000).",
        "q_dob": "What is your date of birth? Type it as DD-MM-YYYY (e.g. 15-07-2010), or reply SKIP.",
        "o_class_X": "Class 10 (going to Class 11)",
        "o_class_XII": "Class 12 (going to college)",
        "o_class_other": "Other / still studying",
        "o_dont_know": "Don't know",
        "o_skip": "Skip",
        "cat_General": "General",
        "cat_Minority": "Minority",
        "g_Female": "Female", "g_Male": "Male", "g_Transgender": "Transgender",
        "inc_100000": "Up to ₹1 lakh",
        "inc_250000": "₹1 – 2.5 lakh",
        "inc_350000": "₹2.5 – 3.5 lakh",
        "inc_450000": "₹3.5 – 4.5 lakh",
        "inc_800000": "₹4.5 – 8 lakh",
        "inc_800001": "Above ₹8 lakh",
        "invalid": "Sorry, I did not understand that. Please reply with one of the numbers below.",
        "invalid_dob": "Please type your date of birth as DD-MM-YYYY (e.g. 15-07-2010), or reply SKIP.",
        "class_other": ("Right now I can only help students who have passed Class 10 or Class 12. "
                        "You can explore all scholarships at https://scholarships.gov.in/ .\nReply HI any time to start again."),
        "results_head": "Based on your answers, here are {n} scholarship(s) you can explore (showing {a}–{b} of {total}):",
        "results_none": ("I could not find a scheme in our list that matches all your answers. "
                         "You can still explore https://scholarships.gov.in/ ."),
        "results_foot": ("ℹ️ This list is based only on your answers and the Scholarship Eligibility Rule V3.0. "
                         "Final eligibility is decided by the scheme's department when you apply."),
        "benefit": "Benefit", "apply": "Apply / info", "apply_unverified": "info (portal link not yet verified)",
        "o_more": "Show more schemes",
        "o_restart": "Start again",
        "o_help": "Help",
        "no_more": "That was the full list. Reply HI to start again.",
        "help": ("I help you find government scholarships in 2 minutes.\n"
                 "• Reply with the number of your choice.\n"
                 "• HI or RESTART – start again\n• HELP – this message\n• STOP – stop messages\n"
                 "Your answers are used only to suggest schemes. Official portal: https://scholarships.gov.in/"),
        "stopped": "You will not get more messages from us. Reply HI any time to start again.",
        "summary": "Your answers: {facts}",
        "f_class_passed": "Class passed", "f_state": "State/UT", "f_category": "Category", "f_gender": "Gender",
        "f_annual_family_income": "Family income", "f_dob": "Date of birth",
        "reply_number": "Reply with a number:",
        "o_feedback": "Rate this service & get your share link",
        "q_rating": "How useful was this? Reply 1 (not useful) to 5 (very useful).",
        "q_comment": "Thank you! Any comment or suggestion? Type it, or reply SKIP.",
        "share": ("🙏 Thanks for your feedback!\nKnow a friend who passed Class 10 or 12? Share your personal link:\n"
                  "WhatsApp: {wa}\nWeb: {web}\nOr ask them to send the code *{code}* to this number."),
        "share_no_wa": "(WhatsApp link available once the WhatsApp number is set up)",
    },
    "hi": {
        "welcome_named": "नमस्ते {name}! 👋 मैं MoSJE छात्रवृत्ति खोज सहायक हूँ।",
        "welcome": "नमस्ते! 👋 मैं MoSJE छात्रवृत्ति खोज सहायक हूँ।",
        "intro": "कुछ आसान सवालों के जवाब दीजिए (लगभग 2 मिनट), और मैं आपको वे छात्रवृत्तियाँ दिखाऊँगा जिनके बारे में आप जानकारी ले सकते हैं।",
        "choose_lang": "Please choose your language / कृपया भाषा चुनें:",
        "prefill": "आपके रिकॉर्ड से हमें यह जानकारी मिली है:\n{facts}\nक्या यह सही है?",
        "prefill_yes": "हाँ, सही है",
        "prefill_no": "नहीं, मैं जवाब दूँगा/दूँगी",
        "q_class_passed": "आपने हाल ही में कौन सी कक्षा पास की है?",
        "q_state": "आप किस राज्य/केंद्र शासित प्रदेश के निवासी हैं? नंबर भेजें या नाम लिखें।",
        "q_category": "आपकी सामाजिक श्रेणी क्या है?",
        "q_gender": "आपका लिंग क्या है?",
        "q_annual_family_income": "आपके परिवार की कुल वार्षिक आय कितनी है? कोई सीमा चुनें या राशि लिखें (जैसे 180000)।",
        "q_dob": "आपकी जन्म तिथि क्या है? DD-MM-YYYY में लिखें (जैसे 15-07-2010), या SKIP लिखें।",
        "o_class_X": "कक्षा 10 (कक्षा 11 में जा रहे हैं)",
        "o_class_XII": "कक्षा 12 (कॉलेज जा रहे हैं)",
        "o_class_other": "अन्य / अभी पढ़ रहे हैं",
        "o_dont_know": "पता नहीं",
        "o_skip": "छोड़ें",
        "cat_General": "सामान्य",
        "cat_Minority": "अल्पसंख्यक",
        "g_Female": "महिला", "g_Male": "पुरुष", "g_Transgender": "ट्रांसजेंडर",
        "inc_100000": "₹1 लाख तक",
        "inc_250000": "₹1 – 2.5 लाख",
        "inc_350000": "₹2.5 – 3.5 लाख",
        "inc_450000": "₹3.5 – 4.5 लाख",
        "inc_800000": "₹4.5 – 8 लाख",
        "inc_800001": "₹8 लाख से अधिक",
        "invalid": "माफ़ कीजिए, मैं समझ नहीं पाया। कृपया नीचे दिए गए नंबरों में से एक भेजें।",
        "invalid_dob": "कृपया जन्म तिथि DD-MM-YYYY में लिखें (जैसे 15-07-2010), या SKIP लिखें।",
        "class_other": ("अभी मैं केवल कक्षा 10 या कक्षा 12 पास विद्यार्थियों की मदद कर सकता हूँ। "
                        "सभी छात्रवृत्तियाँ https://scholarships.gov.in/ पर देखें।\nफिर से शुरू करने के लिए HI लिखें।"),
        "results_head": "आपके जवाबों के आधार पर ये {n} छात्रवृत्ति(याँ) देखें ({total} में से {a}–{b}):",
        "results_none": "आपके सभी जवाबों से मेल खाती कोई योजना हमारी सूची में नहीं मिली। आप https://scholarships.gov.in/ पर देख सकते हैं।",
        "results_foot": ("ℹ️ यह सूची केवल आपके जवाबों और छात्रवृत्ति पात्रता नियम V3.0 पर आधारित है। "
                         "अंतिम पात्रता आवेदन करने पर योजना का विभाग तय करता है।"),
        "benefit": "लाभ", "apply": "आवेदन / जानकारी", "apply_unverified": "जानकारी (पोर्टल लिंक अभी सत्यापित नहीं)",
        "o_more": "और योजनाएँ दिखाएँ",
        "o_restart": "फिर से शुरू करें",
        "o_help": "मदद",
        "no_more": "पूरी सूची दिखा दी गई है। फिर से शुरू करने के लिए HI लिखें।",
        "help": ("मैं 2 मिनट में सरकारी छात्रवृत्तियाँ खोजने में आपकी मदद करता हूँ।\n"
                 "• अपनी पसंद का नंबर भेजें।\n"
                 "• HI या RESTART – फिर से शुरू\n• HELP – यह संदेश\n• STOP – संदेश बंद करें\n"
                 "आपके जवाब केवल योजनाएँ सुझाने के लिए उपयोग होते हैं। आधिकारिक पोर्टल: https://scholarships.gov.in/"),
        "stopped": "अब आपको हमारे संदेश नहीं मिलेंगे। फिर से शुरू करने के लिए कभी भी HI लिखें।",
        "summary": "आपके जवाब: {facts}",
        "f_class_passed": "पास कक्षा", "f_state": "राज्य/UT", "f_category": "श्रेणी", "f_gender": "लिंग",
        "f_annual_family_income": "पारिवारिक आय", "f_dob": "जन्म तिथि",
        "reply_number": "नंबर भेजें:",
        "o_feedback": "सेवा को रेटिंग दें और अपना शेयर लिंक पाएँ",
        "q_rating": "यह कितना उपयोगी था? 1 (उपयोगी नहीं) से 5 (बहुत उपयोगी) तक नंबर भेजें।",
        "q_comment": "धन्यवाद! कोई टिप्पणी या सुझाव? लिखें, या SKIP भेजें।",
        "share": ("🙏 आपकी प्रतिक्रिया के लिए धन्यवाद!\nक्या आपका कोई दोस्त कक्षा 10 या 12 पास है? अपना लिंक शेयर करें:\n"
                  "WhatsApp: {wa}\nWeb: {web}\nया उनसे यह कोड *{code}* इस नंबर पर भेजने को कहें।"),
        "share_no_wa": "(WhatsApp नंबर सेट होने पर लिंक उपलब्ध होगा)",
    },
}


def t(lang: str, key: str, **kw) -> str:
    s = T.get(lang, T["en"]).get(key) or T["en"].get(key, key)
    return s.format(**kw) if kw else s
