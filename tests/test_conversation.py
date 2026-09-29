from conftest import WA


def test_hindi_flow(client):
    wa = WA(client, "919600000001")
    wa.send("नमस्ते")
    assert "कौन सी कक्षा" in wa.send("2")
    wa.send("2")                     # Class 12
    assert "श्रेणी" in wa.send("Uttar Pradesh")
    wa.send("5")                     # Minority
    wa.send("1")                     # Female
    final = wa.send("1")             # up to 1 lakh
    assert "छात्रवृत्ति" in final and "अंतिम पात्रता" in final


def test_help_stop_restart(client):
    wa = WA(client, "919600000002")
    wa.send("hi")
    wa.send("1")
    h = wa.send("help")
    assert "HI or RESTART" in h and "Which class" in h        # help + current question again
    assert "did not understand" in wa.send("banana")
    assert "will not get more messages" in wa.send("STOP")
    n = len(client.graph.graph_texts("919600000002"))
    wa.send("hello?")                                         # opted out: bot stays silent
    assert len(client.graph.graph_texts("919600000002")) == n
    assert "Discovery Assistant" in wa.send("hi")             # opt back in
    assert "Discovery Assistant" in wa.send("restart")


def test_class_other_ends_politely(client):
    wa = WA(client, "919600000003")
    wa.send("hi")
    wa.send("1")
    assert "Class 10 or Class 12" in wa.send("3")


def test_state_by_typo_and_income_dont_know(client):
    wa = WA(client, "919600000004")
    for m in ["hi", "1", "1", "Maharastra", "3", "2"]:
        wa.send(m)
    final = wa.send("7")
    assert "Don't know" in final and "you can explore" in final


def test_zero_results_message(client, monkeypatch):
    from app.eligibility import engine as E
    monkeypatch.setattr(E.EligibilityEngine, "evaluate", lambda self, f: {
        "rule_version": "V3.0", "as_of": "2026-09-27", "candidate_schemes_checked": 0, "eligible_count": 0,
        "schemes": [], "audit": []})
    wa = WA(client, "919600000005")
    for m in ["hi", "1", "1", "Goa", "1", "1"]:
        wa.send(m)
    assert "could not find" in wa.send("1")
