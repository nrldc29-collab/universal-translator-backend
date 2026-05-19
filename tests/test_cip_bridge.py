from backend.cip_bridge import apply_cip_decision, choose_translation, is_cip_clarification


def test_empty_cip_translation_uses_ut_fallback():
    cip = {"translated": "", "decision": {"type": "response"}}

    assert choose_translation(cip, "hola") == "hola"


def test_cip_translation_overrides_fallback_when_present():
    cip = {"translated": "buenos dias", "decision": {"type": "response"}}

    assert choose_translation(cip, "hola") == "buenos dias"


def test_cip_clarification_sets_response_flags():
    cip = {"translated": "", "decision": {"type": "clarification", "message": "Can you rephrase that?"}}
    response = {}

    apply_cip_decision(response, cip)

    assert is_cip_clarification(cip)
    assert response["translated_by"] == "UT"
    assert response["clarify"] is True
    assert response["clarify_message"] == "Can you rephrase that?"
    assert response["cip_decision"] == cip["decision"]


def test_cip_translation_marks_translated_by_cip():
    response = {}

    apply_cip_decision(response, {"translated": "hola", "decision": {"type": "response"}})

    assert response["translated_by"] == "CIP"


def test_local_cip_metadata_is_added_to_response():
    response = {}
    cip = {
        "translated": "hola",
        "translation_source": "UT+CIP",
        "provider": "local",
        "confidence": 0.88,
        "analysis": {"intent": "statement"},
        "response_plan": {"action": "translate_and_speak"},
        "decision": {"type": "response"},
    }

    apply_cip_decision(response, cip)

    assert response["translated_by"] == "UT+CIP"
    assert response["cip_provider"] == "local"
    assert response["cip_confidence"] == 0.88
    assert response["cip_analysis"] == {"intent": "statement"}
    assert response["cip_response_plan"] == {"action": "translate_and_speak"}
