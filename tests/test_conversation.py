from conftest import EN, HI, WA, wa_answers, wa_start


def test_hindi_flow(client):
    wa = WA(client, "919600000001")
    first = wa.send("नमस्ते")
    assert "भाषा" in first or "language" in first
    consent = wa.send(HI)
    assert "सहमत हूँ" in consent                              # consent in Hindi, Agree / Don't agree
    q1 = wa.send("1")
    assert "(1/5)" in q1 and "किस राज्य की छात्रवृत्तियाँ" in q1   # (1/5) State first (Update 2)
    assert "पढ़ाई का स्तर" in wa.send("Uttar Pradesh")        # (2/5) education level
    wa.send("3")                                              # Class 12 passed
    wa.send("2")                                              # Female
    wa.send("1")                                              # up to ₹10,000 a month
    summary = wa.send("5")                                    # Minority
    assert "जाँच" in summary and "आगे बढ़ें" in summary and "जानकारी बदलें" in summary
    assert "मुख्य मेनू" not in summary                         # summary: Proceed / Edit details only
    assert summary.index("Uttar Pradesh") < summary.index("पढ़ाई का स्तर")   # State listed first
    final = wa.send("1")                                      # Proceed
    assert "छात्रवृत्ति" in final and "अंतिम पात्रता" in final


def test_help_stop_restart(client):
    wa = WA(client, "919600000002")
    q1 = wa_start(wa)
    assert "(1/5) Which state's scholarships would you like to see?" in q1
    h = wa.send("help")
    assert "BACK – previous step" in h and "Which state's scholarships" in h  # help + current question again
    assert "didn't get that" in wa.send("banana")
    assert "will not get more messages" in wa.send("STOP")
    n = len(client.graph.graph_texts("919600000002"))
    wa.send("hello?")                                         # opted out: bot stays silent
    assert len(client.graph.graph_texts("919600000002")) == n
    back = wa.send("hi")                                      # opt back in: language kept, consent asked again
    assert "Discovery Assistant" in back and "Agree" in back
    assert "Discovery Assistant" in wa.send("restart")


def test_class_other_ends_politely(client):
    wa = WA(client, "919600000003")
    wa_start(wa)
    assert "(2/5)" in wa.send("Bihar")
    out = wa.send("6")                                        # Other / not studying -> ends at once
    assert "Class 1 up to Post Graduation" in out and "(3/5)" not in out


def test_state_by_typo_and_typed_income(client):
    wa = WA(client, "919600000004")
    wa_start(wa)
    assert "(2/5)" in wa.send("Maharastra")                   # typo fixed
    for m in ["3", "1"]:
        wa.send(m)
    wa.send("8000")                                           # typed monthly income -> first band
    summary = wa.send("3")
    assert "Maharashtra" in summary and "₹96,000 a year" in summary
    assert "you can explore" in wa.send("Proceed")


def test_zero_results_message(client, monkeypatch):
    from app.eligibility import engine as E
    monkeypatch.setattr(E.EligibilityEngine, "evaluate", lambda self, f: {
        "rule_version": "V3.0", "as_of": "2026-09-27", "candidate_schemes_checked": 0, "eligible_count": 0,
        "schemes": [], "audit": []})
    wa = WA(client, "919600000005")
    wa_start(wa)
    out = wa_answers(wa, state="Goa")
    assert "could not find" in out and "Edit details" in out and "o_" not in out
