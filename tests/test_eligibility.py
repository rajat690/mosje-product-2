from app.eligibility import get_engine
from app.eligibility.engine import (ELIGIBLE, NOT_ELIGIBLE, check_education_stage, derive_education_stage,
                                    evaluate_pair, profile_from_facts)
from app.eligibility.rules_compiler import compile_row

STUDENT = {"state": "Rajasthan", "class_passed": "X", "category": "SC", "gender": "Male",
           "annual_family_income": 180000, "dob": "2010-07-15"}


def scheme(**over):
    row = {"Programme / Scheme Name": "Test scheme", "Level": "State", "State / UT / Central": "Rajasthan",
           "Education Stage (Rule 6)": "Post-Matric", "Age Requirement (from DOB)": "Not specified",
           "Gender Requirement": "All", "Family Income Requirement": "Up to ₹2.5 lakh",
           "Social Category Requirement (SC/ST/OBC/General/Minority)": "SC", "Verification Status": "Verified"}
    row.update(over)
    return compile_row(row, 1)


def test_master_loaded_547_rows():
    e = get_engine()
    assert len(e.all_rules) == 547
    assert len(e.rules) == 525          # 22 superseded / placeholder rows excluded


def test_rule_example_eligible():
    assert evaluate_pair(profile_from_facts(STUDENT), scheme())["Final_Result"] == ELIGIBLE


def test_rule_failure_example_category():
    a = evaluate_pair(profile_from_facts(STUDENT), scheme(**{"Social Category Requirement (SC/ST/OBC/General/Minority)": "ST"}))
    assert a["Final_Result"] == NOT_ELIGIBLE and a["Social_Category_Result"] == "FAIL"


def test_rule_failure_example_stage():
    s = scheme(**{"Education Stage (Rule 6)": "Higher Education"})
    assert evaluate_pair(profile_from_facts(STUDENT), s)["Final_Result"] == NOT_ELIGIBLE
    xii = dict(STUDENT, class_passed="XII")
    assert evaluate_pair(profile_from_facts(xii), s)["Final_Result"] == ELIGIBLE


def test_stage_quick_reference():
    x, xii = derive_education_stage("X"), derive_education_stage("XII")
    assert x == {"Post-Matric"} and xii == {"Post-Matric", "Higher Education"}
    assert derive_education_stage("VIII") is None
    p = profile_from_facts({"class_passed": "IX"})
    assert check_education_stage(p, scheme())[0] == "FAIL"


def test_jurisdiction_other_state_excluded():
    e = get_engine()
    res = e.evaluate(STUDENT)
    states = {c["state_ut"] for c in res["schemes"]}
    assert states <= {"Central", "Rajasthan"}
    assert res["eligible_count"] > 0


def test_income_unknown_fails_income_schemes_only():
    s = scheme()
    no_inc = dict(STUDENT)
    no_inc.pop("annual_family_income")
    assert evaluate_pair(profile_from_facts(no_inc), s)["Income_Result"] == "FAIL"
    s2 = scheme(**{"Family Income Requirement": "Not specified"})
    assert evaluate_pair(profile_from_facts(no_inc), s2)["Final_Result"] == ELIGIBLE


def test_income_ceiling():
    rich = dict(STUDENT, annual_family_income=300000)
    assert evaluate_pair(profile_from_facts(rich), scheme())["Income_Result"] == "FAIL"


def test_needed_facts_derived_from_master():
    need = get_engine().needed_facts()
    # max 5 discovery questions, fixed order (Update 2: State/UT first, then education, gender, income, category)
    assert need == ["state", "class_passed", "gender", "annual_family_income", "category"]
    # the V3.0 master has no computable age rule, so DOB is not asked
    assert "dob" not in need
