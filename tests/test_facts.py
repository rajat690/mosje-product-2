from app import facts as F
from app.conversation.core import inr


def test_mobile():
    assert F.norm_mobile("98765 43210") == "919876543210"
    assert F.norm_mobile("+91-98765-43210") == "919876543210"
    assert F.norm_mobile("09876543210") == "919876543210"
    assert F.norm_mobile("12345") is None
    assert F.mask_mobile("919876543210") == "91••••••3210"


def test_state_aliases():
    assert F.norm_state("rajasthan") == "Rajasthan"
    assert F.norm_state("NCT of Delhi") == "Delhi"
    assert F.norm_state("Orissa") == "Odisha"
    assert F.norm_state("Rajastan") == "Rajasthan"
    assert F.norm_state("राजस्थान") == "Rajasthan"
    assert F.norm_state("Atlantis") is None


def test_income_and_others():
    assert F.norm_income("1.8 lakh") == 180000
    assert F.norm_income("₹2,50,000") == 250000
    assert F.norm_income("180k") == 180000
    assert F.norm_income("abc") is None
    assert F.norm_class("Class 12") == "XII" and F.norm_class("10th") == "X"
    assert F.norm_category("gen") == "General"
    assert F.norm_gender("F") == "Female"
    assert F.norm_dob("15-07-2010") == "2010-07-15"
    assert inr(250000) == "₹2,50,000" and inr(12345678) == "₹1,23,45,678"


def test_normalise_facts_warns():
    facts, warns = F.normalise_facts({"state": "Rajasthan", "class": "10", "category": "XYZ", "income": "2 lakh"})
    assert facts == {"state": "Rajasthan", "class_passed": "X", "annual_family_income": 200000}
    assert any("category" in w for w in warns)
