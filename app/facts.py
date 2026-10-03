"""Normalisers for student facts, shared by referrals (API/CSV) and the conversation."""
from __future__ import annotations

import difflib
import re
from datetime import date, datetime
from typing import Optional

from .eligibility import get_engine

CATEGORIES = ["SC", "ST", "OBC", "General", "Minority"]
GENDERS = ["Female", "Male", "Transgender"]

STATE_ALIASES = {
    "nct of delhi": "Delhi", "new delhi": "Delhi", "delhi nct": "Delhi", "dl": "Delhi",
    "orissa": "Odisha", "pondicherry": "Puducherry", "pondy": "Puducherry",
    "j&k": "Jammu and Kashmir", "j & k": "Jammu and Kashmir", "jammu & kashmir": "Jammu and Kashmir", "jk": "Jammu and Kashmir",
    "andaman & nicobar": "Andaman and Nicobar Islands", "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
    "daman and diu": "Dadra & Nagar Haveli and Daman & Diu", "dadra and nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
    "dnh": "Dadra & Nagar Haveli and Daman & Diu", "dnhdd": "Dadra & Nagar Haveli and Daman & Diu",
    "dadra and nagar haveli and daman and diu": "Dadra & Nagar Haveli and Daman & Diu",
    "up": "Uttar Pradesh", "mp": "Madhya Pradesh", "tn": "Tamil Nadu", "wb": "West Bengal", "ap": "Andhra Pradesh",
    "hp": "Himachal Pradesh", "uk": "Uttarakhand", "uttaranchal": "Uttarakhand", "rj": "Rajasthan", "mh": "Maharashtra",
    "ka": "Karnataka", "gj": "Gujarat", "cg": "Chhattisgarh", "jh": "Jharkhand", "br": "Bihar", "pb": "Punjab",
    "hr": "Haryana", "ts": "Telangana", "tg": "Telangana", "kl": "Kerala", "od": "Odisha", "as": "Assam",
    # Hindi names
    "राजस्थान": "Rajasthan", "उत्तर प्रदेश": "Uttar Pradesh", "मध्य प्रदेश": "Madhya Pradesh", "बिहार": "Bihar",
    "दिल्ली": "Delhi", "महाराष्ट्र": "Maharashtra", "गुजरात": "Gujarat", "हरियाणा": "Haryana", "पंजाब": "Punjab",
    "झारखंड": "Jharkhand", "छत्तीसगढ़": "Chhattisgarh", "उत्तराखंड": "Uttarakhand", "हिमाचल प्रदेश": "Himachal Pradesh",
    "कर्नाटक": "Karnataka", "केरल": "Kerala", "तमिलनाडु": "Tamil Nadu", "पश्चिम बंगाल": "West Bengal", "ओडिशा": "Odisha",
    "असम": "Assam", "तेलंगाना": "Telangana", "आंध्र प्रदेश": "Andhra Pradesh", "गोवा": "Goa",
}


def states() -> list[str]:
    return get_engine().states()


_NATIVE_STATES: dict = {}


def native_state_names() -> dict:
    """State names in Indian scripts -> canonical English name, read from the companion UI language packs
    (app/static/companion/lang/*.json, key "states"), so typed answers like "राजस्थान" or "தமிழ்நாடு" work too."""
    if not _NATIVE_STATES:
        import json
        from pathlib import Path
        for f in sorted((Path(__file__).resolve().parent / "static" / "companion" / "lang").glob("*.json")):
            try:
                for en, nat in (json.loads(f.read_text(encoding="utf-8")).get("states") or {}).items():
                    _NATIVE_STATES[re.sub(r"\s+", " ", nat.strip()).lower()] = en
            except (OSError, ValueError):
                continue
        _NATIVE_STATES.setdefault("", "")
    return _NATIVE_STATES


def norm_state(v) -> Optional[str]:
    s = re.sub(r"\s+", " ", str(v or "").strip())
    if not s:
        return None
    low = s.lower()
    for st in states():
        if st.lower() == low:
            return st
    if low in STATE_ALIASES:
        return STATE_ALIASES[low]
    if s in STATE_ALIASES:
        return STATE_ALIASES[s]
    native = native_state_names().get(low)       # 2 Oct: State typed in Hindi/Bengali/Tamil/... script
    if native:
        return native
    close = difflib.get_close_matches(low, [x.lower() for x in states()], n=1, cutoff=0.82)
    if close:
        return next(x for x in states() if x.lower() == close[0])
    return None


def norm_class(v) -> Optional[str]:
    """Education level: PRE (studying Class 1-10), X, XII (passed), UG, PG (studying), OTHER."""
    raw = str(v or "").strip().upper()
    c = re.sub(r"^(STD\.?|STANDARD|CLASS)\s*", "", raw)
    c = re.sub(r"(\d+)\s*(ST|ND|RD|TH)\b", r"\1", c)
    c = re.sub(r"\s*(PASSED|PASS|STANDARD|STD)$", "", c).strip()
    if c in {"X", "10", "MATRIC", "SSLC", "SSC"}:
        return "X"
    if c in {"XII", "12", "HSC", "INTERMEDIATE", "PLUS TWO", "+2"}:
        return "XII"
    if c in {"PRE", "PRE-MATRIC", "PREMATRIC", "SCHOOL"} or c in {str(i) for i in range(1, 10)} or \
            c in {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"}:
        return "PRE"
    if c in {"UG", "GRADUATION", "GRADUATE", "UNDERGRADUATE", "DEGREE", "BACHELOR", "BA", "BSC", "BCOM", "BTECH"}:
        return "UG"
    if c in {"DIPLOMA", "POLYTECHNIC", "ITI"}:      # Update 3: diploma / ITI = after Class 10/12 -> Post-Matric (XII)
        return "XII"
    if c in {"PG", "POST GRADUATION", "POSTGRADUATE", "POST-GRADUATION", "MASTERS", "MASTER", "MA", "MSC", "MCOM",
             "MTECH", "PHD", "M.PHIL", "MPHIL"}:
        return "PG"
    if c in {"OTHER", "NOT STUDYING", "NONE"}:
        return "OTHER"
    return None


def norm_category(v) -> Optional[str]:
    c = str(v or "").strip().lower()
    m = {"sc": "SC", "st": "ST", "obc": "OBC", "general": "General", "gen": "General", "ur": "General",
         "unreserved": "General", "minority": "Minority", "min": "Minority",
         "अनुसूचित जाति": "SC", "अनुसूचित जनजाति": "ST", "अन्य पिछड़ा वर्ग": "OBC", "सामान्य": "General",
         "अल्पसंख्यक": "Minority"}
    return m.get(c)


def norm_gender(v) -> Optional[str]:
    g = str(v or "").strip().lower()
    m = {"f": "Female", "female": "Female", "girl": "Female", "woman": "Female", "महिला": "Female", "लड़की": "Female",
         "m": "Male", "male": "Male", "boy": "Male", "man": "Male", "पुरुष": "Male", "लड़का": "Male",
         "t": "Transgender", "tg": "Transgender", "transgender": "Transgender", "ट्रांसजेंडर": "Transgender"}
    return m.get(g)


_AMOUNT = re.compile(r"^(?:rs\.?|inr|₹)?\s*([\d][\d,]*(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|l|k|thousand|हजार|लाख)?$", re.I)


def norm_income(v) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v) if v >= 0 else None
    s = str(v).strip().lower().replace("rupees", "").replace("per year", "").replace("/year", "").strip()
    m = _AMOUNT.match(s)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit in {"lakh", "lakhs", "lac", "lacs", "l", "लाख"}:
        num *= 100000
    elif unit in {"k", "thousand", "हजार"}:
        num *= 1000
    return int(round(num))


_DOB_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%Y/%m/%d")


def norm_dob(v) -> Optional[str]:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = re.sub(r"\s+", " ", str(v).strip())
    for fmt in _DOB_FORMATS:
        try:
            d = datetime.strptime(s, fmt).date()
            if 1950 <= d.year <= date.today().year:
                return d.isoformat()
        except ValueError:
            continue
    return None


def norm_bool(v) -> Optional[bool]:
    s = str(v if v is not None else "").strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return None


def norm_mobile(v) -> Optional[str]:
    """Return digits with country code (India default): '9876543210' -> '919876543210'."""
    d = re.sub(r"\D", "", str(v or ""))
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 11 and d.startswith("0"):
        d = "91" + d[1:]
    if len(d) == 10 and d[0] in "6789":
        d = "91" + d
    if 11 <= len(d) <= 15:
        return d
    return None


def mask_mobile(m: Optional[str]) -> str:
    if not m:
        return ""
    return m[:2] + "•" * max(0, len(m) - 6) + m[-4:] if len(m) > 6 else "••••"


def first_name(name: Optional[str]) -> Optional[str]:
    n = str(name or "").strip()
    return n.split()[0].title() if n else None


FACT_KEYS = ["state", "class_passed", "category", "gender", "annual_family_income", "dob", "disability"]


def normalise_facts(raw: dict) -> tuple[dict, list[str]]:
    """Normalise optional known facts. Returns (facts, warnings). Unknown values are dropped with a warning."""
    facts, warns = {}, []
    checks = [("state", norm_state), ("class_passed", norm_class), ("category", norm_category),
              ("gender", norm_gender), ("annual_family_income", norm_income), ("dob", norm_dob),
              ("disability", norm_bool)]
    aliases = {"class_passed": ["class", "class_passed"], "annual_family_income": ["income", "annual_family_income"],
               "state": ["state", "domicile_state"]}
    for key, fn in checks:
        val = None
        for k in aliases.get(key, [key]):
            if raw.get(k) not in (None, ""):
                val = raw.get(k)
                break
        if val is None:
            continue
        n = fn(val)
        if n is None:
            warns.append(f"{key}: value '{val}' not recognised, ignored")
        else:
            facts[key] = n
    return facts, warns
