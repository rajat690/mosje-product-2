"""Re-compile data/MoSJE_Scholarship_Master_V3.0.xlsx into data/scheme_rules_v3.json.

Run after replacing the scheme master:  python tools/compile_master.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.eligibility import settings  # noqa: E402
from app.eligibility.engine import write_rules_json  # noqa: E402
from app.eligibility.rules_compiler import compile_master  # noqa: E402

rules = compile_master(settings.SCHEME_MASTER_PATH)
write_rules_json(rules)
print(f"{len(rules)} schemes compiled -> {settings.SCHEME_RULES_JSON}")
print(Counter(r.Active_Status for r in rules), Counter(r.Compile_Status for r in rules))
