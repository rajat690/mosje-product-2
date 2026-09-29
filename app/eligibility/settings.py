"""Eligibility settings for Product 2 (values from Scholarship Eligibility Rule V3.0)."""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("P2_DATA_DIR", ROOT / "data"))
SCHEME_MASTER_PATH = Path(os.environ.get("SCHEME_MASTER_PATH", DATA_DIR / "MoSJE_Scholarship_Master_V3.0.xlsx"))
SCHEME_RULES_JSON = Path(os.environ.get("SCHEME_RULES_JSON", DATA_DIR / "scheme_rules_v3.json"))
SCHEME_MASTER_SHEET = "Fresh Scholarship Master"

RULE_VERSION = "V3.0"
EFFECTIVE_FROM = "2026-09-27"


def as_of_date() -> date:
    """Discovery is live, so age is calculated as of today unless ELIGIBILITY_AS_OF is set."""
    v = os.environ.get("ELIGIBILITY_AS_OF")
    return date.fromisoformat(v) if v else date.today()
