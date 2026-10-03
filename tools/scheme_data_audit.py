"""Scheme data audit (Update 3, 29 Sep 2026).

Checks the compiled scheme rules for contradictions between the scheme NAME and the fields the bot
filters on (education level, gender, social category, State, income), runs a matrix of student
profiles, and lists every value the Product 2 overlay changes compared with the master Excel.

    python tools/scheme_data_audit.py [--before OLD_scheme_rules.json] [--xlsx out.xlsx] [--md docs/SCHEME_DATA_AUDIT.md]

--before: a previously deployed data/scheme_rules_v3.json, to count "before vs after".
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.eligibility.engine import EligibilityEngine, load_rules, rule_from_json  # noqa: E402
from app.eligibility.overlay import (CURATED, LEVELS, STAGE_LEVELS, infer_categories,  # noqa: E402
                                     infer_gender, resolve_education)
from app.eligibility.rules_compiler import NO_REQ, PARSED, compile_master  # noqa: E402

STATES = ["Andaman and Nicobar", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh",
          "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
          "Kerala", "Lakshadweep", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
          "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
          "Uttar Pradesh", "Uttarakhand", "West Bengal"]
LEVEL_LABEL = {"PRE": "Class 1-10", "X": "Class 10 passed", "XII": "Class 12 passed", "UG": "UG", "PG": "PG"}
BANDS = {"m10k": (None, 120000), "m30k": (120001, 360000), "gt30k": (360001, None)}


def cur_for(name):
    low = name.lower()
    return next((v for k, v in CURATED if k in low), None)


def name_level(r):
    codes, _stage, src = resolve_education(r.Scheme_Name, "", "Not specified", frozenset())
    return codes, src


def name_gender(r):
    c = cur_for(r.Scheme_Name)
    return c["gender"] if c and "gender" in c else infer_gender(r.Scheme_Name)


def name_cats(r):
    c = cur_for(r.Scheme_Name)
    return set(c["categories"]) if c and "categories" in c else infer_categories(r.Scheme_Name)[0]


def reachable_levels(r):
    out = set()
    for lv in LEVELS:
        if r.level_code_set and lv not in r.level_code_set:
            continue
        if r.Education_Stage_Status == PARSED and not (
                set().union(*(STAGE_LEVELS[x] for x in r.stage_set)) & {lv}):
            continue
        if r.Education_Stage_Status not in (PARSED, NO_REQ):
            continue
        out.add(lv)
    return out


def effective_gender(r):
    return set() if r.Gender_Status == NO_REQ else set(r.gender_set)


def effective_cats(r):
    return set() if r.Category_Status == NO_REQ else set(r.category_set)


def mismatches(r):
    """List of (type, detail) contradictions between the scheme name and what the bot filters on."""
    out = []
    reach = reachable_levels(r)
    nl, src = name_level(r)
    if not reach:
        out.append(("education", "no student level can see this scheme (level and stage contradict)"))
    elif nl and reach - nl:
        out.append(("education", f"name says {'/'.join(x for x in LEVELS if x in nl)} ({src}); bot shows it to "
                                 f"{'/'.join(x for x in LEVELS if x in reach)}"))
    g = name_gender(r)
    eg = effective_gender(r)
    if g in ("Male", "Female") and eg != {g}:
        out.append(("gender", f"name says {g}; bot uses {'/'.join(sorted(eg)) or 'All'}"))
    if g == "All" and eg:
        out.append(("gender", f"name says boys and girls; bot uses {'/'.join(sorted(eg))}"))
    c = name_cats(r)
    ec = effective_cats(r)
    if c and ec != c:
        out.append(("category", f"name says {', '.join(sorted(c))}; bot uses {', '.join(sorted(ec)) or 'All'}"))
    named = [s for s in STATES if re.search(r"\b" + re.escape(s) + r"\b", r.Scheme_Name)]
    if r.Scheme_Level == "Central":
        bad = [s for s in named if s not in (r.Region_States or "") and s != "Assam"]   # 'Assam Rifles' is a force
    else:
        bad = [s for s in named if s.lower() not in r.Scheme_State_UT.lower()]
    if bad:
        out.append(("state", f"name mentions {', '.join(bad)}; scheme is {r.Scheme_State_UT}"))
    if r.Income_Status not in (PARSED, NO_REQ) or (r.Income_Max is not None and r.Income_Max <= 0):
        out.append(("income", f"income value not usable: '{r.Income_Raw}'"))
    return out


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return [rule_from_json(d) for d in json.load(f)["rules"]]


def profiles():
    for lv in LEVELS:
        for st in ["Karnataka", "Rajasthan", "Maharashtra", "Bihar", "West Bengal", "Tamil Nadu"]:
            for g in ["Male", "Female"]:
                for cat in ["SC", "ST", "OBC", "General", "Minority"]:
                    for band in ["m10k", "m30k"]:
                        lo, hi = BANDS[band]
                        yield {"state": st, "class_passed": lv, "gender": g, "category": cat,
                               "annual_family_income": hi, "income_min": lo, "_band": band}


def matrix(rules):
    eng = EligibilityEngine(rules)
    by_id = {r.Scheme_ID: r for r in rules}
    total, bad, n, examples = 0, Counter(), 0, []
    for f in profiles():
        n += 1
        res = eng.evaluate({k: v for k, v in f.items() if not k.startswith("_")})
        for sc in res["schemes"]:
            total += 1
            r = by_id[sc["scheme_id"]]
            lv = f["class_passed"]
            nl, _ = name_level(r)
            if nl and lv not in nl:
                bad["education"] += 1
                if len(examples) < 8:
                    examples.append(f"{f['state']} {lv} {f['gender']} {f['category']}: {r.Scheme_Name}")
            g = name_gender(r)
            if g in ("Male", "Female") and f["gender"] != g:
                bad["gender"] += 1
            c = name_cats(r)
            if c and f["category"] not in c:
                bad["category"] += 1
    return n, total, bad, examples


def ka_pg(rules):
    eng = EligibilityEngine(rules)
    res = eng.evaluate({"state": "Karnataka", "class_passed": "PG", "gender": "Male", "category": "General",
                        "annual_family_income": 360000, "income_min": 120001})
    return res["eligible_count"], [s["name"] for s in res["schemes"][:5]]


FIELDS = [
    ("Education level (bot codes)", lambda r: r.Level_Codes or "(none – broad stage only)"),
    ("Education stage (Rule 6)", lambda r: r.Education_Stage_Allowed),
    ("Social category", lambda r: r.Categories_Allowed if r.Category_Status != NO_REQ else "All"),
    ("Gender", lambda r: r.Gender_Allowed if r.Gender_Status != NO_REQ else "All"),
    ("Only for (target group)", lambda r: r.Target_Groups),
    ("Region (Central scheme)", lambda r: r.Region_States),
]


def reason_for(field, r):
    key = {"Education level (bot codes)": "education level", "Education stage (Rule 6)": "education stage",
           "Social category": "category", "Gender": "gender", "Only for (target group)": "only for",
           "Region (Central scheme)": "region"}[field]
    parts = [p for p in (r.Overlay_Notes or "").split(" | ") if p.startswith(key)]
    return parts[0] if parts else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before")
    ap.add_argument("--headcode", help="rules compiled with the previous overlay code (to label the source of a change)")
    ap.add_argument("--xlsx")
    ap.add_argument("--md")
    a = ap.parse_args()
    after = [r for r in load_rules()]
    raw = {r.Scheme_ID: r for r in compile_master(overlay=False)}
    before = load_json(a.before) if a.before else None
    bmap = {r.Scheme_ID: r for r in before} if before else {}
    hmap = {r.Scheme_ID: r for r in load_json(a.headcode)} if a.headcode else {}
    active = [r for r in after if r.Active_Status == "ACTIVE"]

    def mm_counts(rules):
        c, rows = Counter(), []
        for r in rules:
            if r.Active_Status != "ACTIVE":
                continue
            for t, d in mismatches(r):
                c[t] += 1
                rows.append((r, t, d))
        return c, rows

    after_c, after_rows = mm_counts(after)
    before_c, before_rows = mm_counts(before) if before else (Counter(), [])

    changes = []
    for r in active:
        m = raw[r.Scheme_ID]
        for field, fn in FIELDS:
            old, new = fn(m), fn(r)
            if old != new:
                live = fn(bmap[r.Scheme_ID]) if bmap else ""
                changes.append({"Scheme ID": r.Scheme_ID, "Scheme name": r.Scheme_Name, "State/Central": r.Scheme_State_UT,
                                "Field": field, "Value from master Excel as compiled (no overlay)": old, "New value used by bot": new,
                                "Live bot before this fix": live,
                                "Changed in this fix (vs live)": "Yes" if bmap and live != new else "No",
                                "Introduced by": ("already live (Update 1 overlay)" if bmap and live == new else
                                                  "GitHub commit f1cf76d overlay, first compiled now"
                                                  if hmap and fn(hmap[r.Scheme_ID]) == new else "this fix (Update 3)"),
                                "Reason": reason_for(field, r),
                                "Master 'Education Level / Stage'": r.Education_Level_Raw})
    schemes_changed = len({c["Scheme ID"] for c in changes})
    new_fix = [c for c in changes if c["Changed in this fix (vs live)"] == "Yes"]

    print(f"active schemes checked: {len(active)}")
    print(f"name/field mismatches BEFORE: {dict(before_c)} total {sum(before_c.values())}")
    print(f"name/field mismatches AFTER : {dict(after_c)} total {sum(after_c.values())}")
    for r, t, d in after_rows:
        print("  remaining:", r.Scheme_ID, t, d, "|", r.Scheme_Name)
    mb = matrix(before) if before else None
    ma = matrix(after)
    if mb:
        print(f"matrix BEFORE: {mb[0]} profiles, {mb[1]} results, contradictions {dict(mb[2])}")
        for e in mb[3]:
            print("   e.g.", e)
    print(f"matrix AFTER : {ma[0]} profiles, {ma[1]} results, contradictions {dict(ma[2])}")
    kb = ka_pg(before) if before else None
    ka = ka_pg(after)
    if kb:
        print("Karnataka PG before:", kb)
    print("Karnataka PG after:", ka)
    print("introduced by:", Counter(c["Introduced by"] for c in changes))
    print("new-in-fix by field:", Counter(c["Field"] for c in new_fix))
    print(f"overrides vs master: {len(changes)} values on {schemes_changed} schemes; new in this fix: "
          f"{len(new_fix)} values on {len({c['Scheme ID'] for c in new_fix})} schemes")

    if a.xlsx:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Changes"
        cols = list(changes[0].keys()) if changes else []
        ws.append(cols)
        for c in sorted(changes, key=lambda c: (c["Changed in this fix (vs live)"] != "Yes", c["Scheme ID"], c["Field"])):
            ws.append([c[k] for k in cols])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
        widths = [11, 60, 16, 26, 28, 28, 28, 14, 34, 80, 30]
        for i, w in enumerate(widths):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        s = wb.create_sheet("Summary")
        s.append(["Item", "Before (live)", "After"])
        s.append(["Active schemes checked", len(active), len(active)])
        for t in ["education", "gender", "category", "state", "income"]:
            s.append([f"Name vs data mismatches – {t}", before_c.get(t, 0) if before else "", after_c.get(t, 0)])
        if mb:
            s.append([f"Profile matrix ({ma[0]} profiles): results shown", mb[1], ma[1]])
            for t in ["education", "gender", "category"]:
                s.append([f"Profile matrix: results contradicting the scheme name – {t}", mb[2].get(t, 0), ma[2].get(t, 0)])
        if kb:
            s.append(["Karnataka PG Male General ₹10k–30k/month: results", kb[0], ka[0]])
            for i in range(5):
                s.append([f"  #{i + 1}", kb[1][i] if i < len(kb[1]) else "", ka[1][i] if i < len(ka[1]) else ""])
        s.append(["Overlay values differing from the master Excel (all updates)", "", len(changes)])
        s.append(["...of which changed in this fix", "", len(new_fix)])
        for cell in s[1]:
            cell.font = Font(bold=True)
        s.column_dimensions["A"].width = 70
        s.column_dimensions["B"].width = 55
        s.column_dimensions["C"].width = 55
        rem = wb.create_sheet("Remaining flags")
        rem.append(["Scheme ID", "Scheme name", "Type", "Detail"])
        for r, t, d in after_rows:
            rem.append([r.Scheme_ID, r.Scheme_Name, t, d])
        wb.save(a.xlsx)
        print("wrote", a.xlsx)
    return dict(active=len(active), before_c=before_c, after_c=after_c, mb=mb, ma=ma, kb=kb, ka=ka,
                changes=changes, new_fix=new_fix)


if __name__ == "__main__":
    main()
