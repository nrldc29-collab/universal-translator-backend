from backend.cip_engine import evaluate_local_cip


def test_local_cip_keeps_good_translation_fast_path():
    result = evaluate_local_cip(
        "hello how are you",
        "es",
        fallback_translation="hola como estas",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert result["provider"] == "local"
    assert result["translated"] == "hola como estas"
    assert result["decision"]["type"] == "response"
    assert result["confidence"] > 0.7


def test_local_cip_clarifies_low_confidence_ambiguous_turn():
    result = evaluate_local_cip(
        "check the charge",
        "es",
        fallback_translation="[en->es] check the charge",
        stt_confidence=0.35,
        translation_confidence=0.2,
    )

    assert result["translated"] == ""
    assert result["decision"]["type"] == "clarification"
    assert result["analysis"]["ambiguity"]["words"]
