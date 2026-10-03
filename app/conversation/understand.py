"""Understand typed answers (Update 3, Product Vision V1.0 section 9: "understand typed answers like
'I am in 2nd year BA'").

Rule-based and offline on purpose (no LLM call, no data leaves the server). Used by the conversation engine as a
fallback when a reply is not one of the offered options, and by the web companion's "You mean X, right?" confirm
step (POST /v1/companion/sessions/{id}/interpret).

    understand("class_passed", "I am in 2nd year BA")  -> "UG"
    understand("state", "from bihar")                  -> "Bihar"
    extract_all("SC girl from Bihar doing BSc, income 8000 a month")
        -> {"category": "SC", "gender": "Female", "state": "Bihar", "class_passed": "UG", "annual_family_income": 96000}
"""
from __future__ import annotations

import re
from typing import Optional

from .. import facts as F

_W = r"(?<![a-z0-9])"          # word start (latin)
_E = r"(?![a-z])"           # word end

EDU_RX: list[tuple[str, re.Pattern]] = [
    ("PG", re.compile(_W + r"(m\.?\s?a|m\.?\s?sc|m\.?\s?com|m\.?\s?tech|m\.?\s?e|mba|mca|m\.?\s?phil|ph\.?\s?d|llm|"
                      r"post\s*-?\s*grad\w*|masters?|pg|doctorate|research scholar)" + _E + r"|स्नातकोत्तर|पीएचडी|एमए", re.I)),
    ("UG", re.compile(_W + r"(b\.?\s?a|b\.?\s?sc|b\.?\s?com|b\.?\s?tech|b\.?\s?e|bba|bca|b\.?\s?ed|b\.?\s?pharm|mbbs|bds|"
                      r"llb|bams|bhms|nursing|b\.?\s?arch|grad\w*|under\s*-?\s*grad\w*|bachelor\w*|degree|college|ug|"
                      r"engineering|medical)" + _E + r"|स्नातक|ग्रेजुएशन|बीए|बीएससी|बीकॉम|कॉलेज", re.I)),
    ("XII", re.compile(_W + r"(diploma|polytechnic|iti|12th\s*pass\w*|class\s*12\s*pass\w*|xii\s*pass\w*|"
                       r"passed\s*(class\s*)?(12|xii)(th)?|hsc\s*pass\w*|intermediate\s*pass\w*)" + _E +
                       r"|12वीं पास|बारहवीं पास|डिप्लोमा|आईटीआई|पॉलिटेक्निक", re.I)),
    ("X", re.compile(_W + r"(class\s*(11|12|xi|xii)|(11|12)(th)?\s*(class|std|standard)|(in|studying)\s*(11|12)(th)?|"
                     r"1[12](th)?\s*me|10th\s*pass\w*|class\s*10\s*pass\w*|matric\s*pass\w*|sslc|ssc\s*pass\w*|"
                     r"passed\s*(class\s*)?(10|x)(th)?|intermediate|junior college|plus\s*(one|two)|\+\s*[12])" + _E +
                     r"|10वीं पास|11वीं|12वीं में|ग्यारहवीं|इंटर", re.I)),
    ("PRE", re.compile(_W + r"(class\s*([1-9]|10|i{1,3}|iv|v|vi{0,3}|ix|x)|([1-9]|10)(st|nd|rd|th)\s*(class|std|standard)|"
                       r"school|pre\s*-?\s*matric|studying\s*in\s*([1-9]|10)(th)?)" + _E + r"|स्कूल|कक्षा\s*[1-9]", re.I)),
    ("OTHER", re.compile(_W + r"(not studying|dropped out|drop\s*out|working|job|left studies|no longer studying)" + _E +
                         r"|पढ़ाई छोड़|नहीं पढ़", re.I)),
]

GENDER_RX = [("Female", re.compile(_W + r"(girl|female|woman|daughter|lady|she|her)" + _E + r"|लड़की|महिला|बेटी|छात्रा", re.I)),
             ("Male", re.compile(_W + r"(boy|male|man|son|he|his)" + _E + r"|लड़का|पुरुष|बेटा|छात्र(?!ा)", re.I))]

CAT_RX = [("SC", re.compile(_W + r"(sc|scheduled caste|dalit)" + _E + r"|अनुसूचित जाति|एससी", re.I)),
          ("ST", re.compile(_W + r"(st|scheduled tribe|tribal|adivasi)" + _E + r"|अनुसूचित जनजाति|आदिवासी|एसटी", re.I)),
          ("OBC", re.compile(_W + r"(obc|backward class|bc|ebc|mbc)" + _E + r"|पिछड़ा|ओबीसी", re.I)),
          ("Minority", re.compile(_W + r"(minority|muslim|christian|sikh|parsi|jain|buddhist)" + _E + r"|अल्पसंख्यक|मुस्लिम", re.I)),
          ("General", re.compile(_W + r"(general|gen|open|unreserved|ur|ews)" + _E + r"|सामान्य|जनरल", re.I))]

_MONEY = re.compile(r"(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|l|k|thousand|हजार|लाख)?", re.I)
_YEARLY = re.compile(r"lakh|lac|year|annual|yearly|p\.?a\b|साल|वार्षिक|लाख", re.I)


def _edu(text: str) -> Optional[str]:
    t = text.lower()
    # "2nd year BA", "final year B.Tech" -> UG; "1st year diploma" -> XII; checked most specific first
    for code, rx in EDU_RX:
        if rx.search(t):
            return code
    return F.norm_class(text)


def _state(text: str) -> Optional[str]:
    v = F.norm_state(text)
    if v:
        return v
    low = " " + re.sub(r"[^\w\s&]", " ", text.lower()) + " "
    best = None
    for st in F.states():                         # longest name first so "West Bengal" beats "Bengal"
        if f" {st.lower()} " in low and (best is None or len(st) > len(best)):
            best = st
    if best:
        return best
    for alias, st in F.STATE_ALIASES.items():
        if len(alias) > 3 and alias in low:
            return st
    m = re.search(r"\b(?:from|in|of|state)\s+([a-z][a-z &]{2,30})", low)
    return F.norm_state(m.group(1).strip()) if m else None


def _first(rxs, text) -> Optional[str]:
    hits = [code for code, rx in rxs if rx.search(text)]
    return hits[0] if len(set(hits)) == 1 or hits else None


def _income(text: str) -> Optional[int]:
    v = F.norm_income(text)
    if v is None:
        m = _MONEY.search(text.replace(",", ""))
        if not m:
            return None
        v = F.norm_income((m.group(1) or "") + (m.group(2) or ""))
    if v is None:
        return None
    if not _YEARLY.search(text) and v < 100000:
        v *= 12                                    # the question asks for MONTHLY income
    return v


def understand(key: str, text: str):
    """Best guess for one question from free text, or None."""
    text = (text or "").strip()
    if not text:
        return None
    if key == "class_passed":
        return _edu(text)
    if key == "state":
        return _state(text)
    if key == "gender":
        return F.norm_gender(text) or _first(GENDER_RX, text)
    if key == "category":
        return F.norm_category(text) or _first(CAT_RX, text)
    if key == "annual_family_income":
        return _income(text) if re.search(r"\d", text) else None
    return None


def extract_all(text: str) -> dict:
    """Every fact we can read from one sentence (used to pre-fill later questions; never overrides answers)."""
    out = {}
    for key in ("state", "class_passed", "gender", "category"):
        v = understand(key, text)
        if v:
            out[key] = v
    if re.search(r"income|earn|salary|kamai|आय|कमाई|₹|rs\.?\s*\d|\d+\s*(k|lakh|thousand)", text, re.I):
        v = understand("annual_family_income", text)
        if v is not None:
            out["annual_family_income"] = v
    return out
