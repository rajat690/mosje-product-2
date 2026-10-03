"""Web companion (/companion) UI translations – export for native-speaker review, and import the reviewed file back.

English + Hindi live in app/static/companion/strings.js; other languages in app/static/companion/lang/<code>.json
(keys: strings, docs = document help texts, months, states). All non-English text was MACHINE-DRAFTED and needs review.

  python tools/companion_translations.py export
      -> docs/translations/companion/<code>.csv   (section, key, English, Hindi reference, translation, reviewer columns)
  python tools/companion_translations.py import ta docs/translations/companion/ta.csv
      -> writes the "translation" column back into app/static/companion/lang/ta.json (placeholders checked)
Then run the tests (tests/test_update3_languages.py checks every key, {placeholder} and State name).
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "app" / "static" / "companion"
OUT = ROOT / "docs" / "translations" / "companion"
PH = re.compile(r"\{\w+\}")
COLS = ["section", "key", "english", "hindi_reference", "translation", "reviewer_ok (Y/N)", "reviewer_suggestion",
        "notes"]


def inline_strings() -> dict:
    src = (COMP / "strings.js").read_text(encoding="utf-8")
    body = src[src.index("var T={") + 6: src.rindex("};") + 1]
    return json.loads(re.sub(r'^ (\w+):', r' "\1":', body, flags=re.M))


def inline_docs() -> dict:
    app = (COMP / "app.js").read_text(encoding="utf-8")
    out = {}
    block = app[app.index("var DOCS={"): app.index("};", app.index("var DOCS={"))]
    for key, body in re.findall(r"^ (\w+):\{(.*)\},?$", block, flags=re.M):
        out[key] = {f: json.loads("[" + v + "]") for f, v in re.findall(r'(\w):\[(".*?",".*?")\]', body)}
    return out


def rows_for(code: str) -> list[dict]:
    T, D = inline_strings(), inline_docs()
    pack = json.loads((COMP / "lang" / f"{code}.json").read_text(encoding="utf-8"))
    rows = []
    for k, (en, hi) in T.items():
        rows.append({"section": "strings", "key": k, "english": en, "hindi_reference": hi,
                     "translation": (pack.get("strings") or {}).get(k, "") or (hi if code == "hi" else "")})
    for dk, fields in D.items():
        for f, (en, hi) in fields.items():
            rows.append({"section": "docs", "key": f"{dk}.{f}", "english": en, "hindi_reference": hi,
                         "translation": ((pack.get("docs") or {}).get(dk) or {}).get(f, "") or (hi if code == "hi" else "")})
    if pack.get("months"):
        en_m = "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec"
        rows.append({"section": "months", "key": "months", "english": en_m, "hindi_reference": "",
                     "translation": ",".join(pack["months"]), "notes": "12 short month names, comma separated"})
    for en, nat in (pack.get("states") or {}).items():
        rows.append({"section": "states", "key": en, "english": en, "hindi_reference": "", "translation": nat})
    return rows


def export() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for f in sorted((COMP / "lang").glob("*.json")):
        code = f.stem
        with open(OUT / f"{code}.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=COLS)
            w.writeheader()
            for r in rows_for(code):
                w.writerow({c: r.get(c, "") for c in COLS})
        print("wrote", OUT / f"{code}.csv")


def import_(code: str, path: str) -> None:
    f = COMP / "lang" / f"{code}.json"
    pack = json.loads(f.read_text(encoding="utf-8"))
    T = inline_strings()
    bad = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("reviewer_suggestion") or "").strip() or (r.get("translation") or "").strip()
            if not v:
                continue
            sec, key = r["section"], r["key"]
            if sec == "strings":
                if sorted(PH.findall(v)) != sorted(PH.findall(T.get(key, [""])[0])):
                    bad.append(key)
                    continue
                pack.setdefault("strings", {})[key] = v
            elif sec == "docs":
                dk, fld = key.split(".")
                pack.setdefault("docs", {}).setdefault(dk, {})[fld] = v
            elif sec == "months":
                m = [x.strip() for x in v.split(",")]
                if len(m) == 12:
                    pack["months"] = m
            elif sec == "states":
                pack.setdefault("states", {})[key] = v
    f.write_text(json.dumps(pack, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print("updated", f, "| skipped (placeholders changed):", bad or "none")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        export()
    elif len(sys.argv) == 4 and sys.argv[1] == "import":
        import_(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
