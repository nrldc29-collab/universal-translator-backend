from backend.communication_brain import analyze_communication, derive_adaptive_policy, detect_register, evaluate_translation_brain


def test_register_detection_does_not_match_slang_inside_normal_words():
    assert detect_register("Bonjour") == "neutral"
    assert detect_register("jo") == "informal"


def test_python_brain_matches_ai_comm_ambiguity_behavior():
    result = evaluate_translation_brain(
        "bank right fine charge",
        "es",
        fallback_translation="banco correcto bien cargo",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert result["analysis"]["source"] == "python_ai_brain_v8"
    assert result["analysis"]["ambiguity"]["high"] is True
    assert result["decision"]["type"] == "clarification"
    assert result["translated"] == ""
    assert result["response_plan"]["action"] == "ask_clarification"
    assert result["response_plan"]["meaning_risk_score"] > 0.45
    assert any(option["type"] == "choose_meaning" and option["word"] == "bank" for option in result["response_plan"]["repair_options"])
    assert result["response_plan"]["turn_policy"]["mode"] == "confirm_then_translate"


def test_python_brain_prefers_specific_ambiguity_prompt_for_placeholder():
    result = evaluate_translation_brain(
        "bank right fine charge",
        "es",
        fallback_translation="[en->es] bank right fine charge",
        stt_confidence=0.9,
        translation_confidence=0.2,
    )

    assert result["decision"]["reason"] == "placeholder_translation_ambiguous"
    assert "bank" in result["decision"]["message"]


def test_python_brain_uses_fast_mode_for_urgent_language_even_with_neutral_context():
    result = evaluate_translation_brain(
        "please come right now",
        "es",
        fallback_translation="por favor ven ahora",
        stt_confidence=0.9,
        translation_confidence=0.9,
        semantic_context={"conversation_mood": "neutral"},
    )

    assert result["analysis"]["tone"] == "urgent"
    assert result["analysis"]["communication_state"] == "urgent"
    assert result["decision"]["type"] == "response"
    assert result["decision"]["mode"] == "fast"
    assert result["response_plan"]["priority"] == "high"
    assert result["response_plan"]["turn_policy"]["latency_budget_ms"] <= 700


def test_python_brain_current_question_overrides_previous_request_context():
    result = evaluate_translation_brain(
        "where is the clinic?",
        "es",
        fallback_translation="donde esta la clinica",
        stt_confidence=0.9,
        translation_confidence=0.9,
        semantic_context={"last_intent": "request"},
    )

    assert result["analysis"]["intent"] == "question"


def test_python_brain_preserves_context_memory_signals():
    analysis = analyze_communication(
        "where is the clinic",
        context=[{"original": "we are near the clinic", "translated": "estamos cerca de la clinica"}],
        speaker_context={"history": ["the clinic is nearby"], "turns": 3},
    )

    assert analysis["memory"]["speaker_turns"] == 3
    assert "clinic" in analysis["memory"]["recent_topics"]
    assert analysis["context_match"] > 0.6


def test_python_brain_flags_untranslated_echo():
    result = evaluate_translation_brain(
        "hello how are you",
        "es",
        source_language="en",
        fallback_translation="hello how are you",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert "untranslated_echo" in result["analysis"]["quality_flags"]
    assert result["decision"]["reason"] == "untranslated_echo"
    assert result["translated"] == ""


def test_python_brain_adapts_after_repeated_clarifications():
    context = [
        {
            "original": f"unclear turn {index}",
            "translated": "",
            "metadata": {"cip": {"decision": {"type": "clarification"}}},
        }
        for index in range(4)
    ]

    policy = derive_adaptive_policy(context)

    assert policy["force_clarification"] is True
    assert policy["confidence_threshold"] > 0.42


def test_python_brain_boosts_speed_after_stable_successes():
    context = [
        {
            "original": f"clear turn {index}",
            "translated": "claro",
            "metadata": {"cip": {"decision": {"type": "response"}}},
        }
        for index in range(6)
    ]

    result = evaluate_translation_brain(
        "good morning",
        "es",
        fallback_translation="buenos dias",
        stt_confidence=0.9,
        translation_confidence=0.9,
        context=context,
    )

    assert result["analysis"]["policy"]["response_speed_boost"] is True
    assert result["decision"]["mode"] == "fast"
    assert result["response_plan"]["turn_policy"]["mode"] == "instant_translate"
    assert result["response_plan"]["client_hints"]["tts_mode"] == "stream_now"


def test_python_brain_high_stakes_medical_turn_requires_confirmation_when_uncertain():
    result = evaluate_translation_brain(
        "I need medication dose 20",
        "es",
        source_language="en",
        fallback_translation="necesito medicacion dosis 20",
        stt_confidence=0.7,
        translation_confidence=0.68,
    )

    assert result["analysis"]["domains"]["risk_level"] == "high"
    assert result["analysis"]["communication_state"] == "high_stakes"
    assert result["decision"]["reason"] == "high_stakes_confirmation"
    assert result["response_plan"]["strategy"] == "precision_confirm"
    assert result["response_plan"]["confirm_numbers"] is True
    assert any(option["type"] == "confirm_exact" for option in result["response_plan"]["repair_options"])
    assert result["response_plan"]["conversation_contract"]["requires_exact_confirmation"] is True
    assert result["response_plan"]["turn_policy"]["tts"] == "skip"


def test_python_brain_high_stakes_placeholder_uses_specific_prompt():
    result = evaluate_translation_brain(
        "I need medication dose 20",
        "es",
        source_language="en",
        fallback_translation="[en->es] I need medication dose 20",
        stt_confidence=0.8,
        translation_confidence=0.2,
    )

    assert result["decision"]["reason"] == "placeholder_translation_high_stakes"
    assert "medical" in result["decision"]["message"]


def test_python_brain_speaks_clear_hospital_location_request_immediately():
    result = evaluate_translation_brain(
        "Where is the nearest hospital?",
        "ht",
        source_language="en",
        fallback_translation="Kote lopital ki pi pre a ye?",
        stt_confidence=0.95,
        translation_confidence=0.95,
    )

    assert result["analysis"]["domains"]["risk_level"] == "high"
    assert result["analysis"]["precision_status"]["safe_location_request"] is True
    assert result["analysis"]["precision_status"]["mode"] == "fast_lane"
    assert result["decision"]["type"] == "response"
    assert result["translated"] == "Kote lopital ki pi pre a ye?"
    assert result["response_plan"]["speak"] is True
    assert result["response_plan"]["client_hints"]["skip_tts"] is False


def test_python_brain_financial_amount_uses_precision_plan():
    result = evaluate_translation_brain(
        "the price is $25",
        "es",
        source_language="en",
        fallback_translation="el precio es 25 dolares",
        stt_confidence=0.95,
        translation_confidence=0.95,
    )

    assert "financial" in result["analysis"]["domains"]["high_stakes"]
    assert "precision_entities" in result["analysis"]["quality_flags"]
    assert result["analysis"]["precision_status"]["mode"] == "fast_lane"
    assert result["decision"]["type"] == "response"
    assert result["translated"] == "el precio es 25 dolares"
    assert result["response_plan"]["strategy"] == "precision_fast_lane"
    assert result["response_plan"]["priority"] == "high"
    assert result["response_plan"]["speak"] is True
    assert result["response_plan"]["client_hints"]["skip_tts"] is False
    assert result["response_plan"]["client_hints"]["ask_before_speaking"] is False
    assert result["response_plan"]["turn_policy"]["mode"] == "instant_translate"
    assert result["response_plan"]["conversation_contract"]["requires_exact_confirmation"] is False
    assert result["response_plan"]["conversation_contract"]["allow_partial_translation"] is True


def test_python_brain_speaker_style_prefers_plain_clarifying_language():
    context = [
        {
            "original": f"unclear {index}",
            "translated": "",
            "metadata": {"cip": {"decision": {"type": "clarification"}}},
        }
        for index in range(3)
    ]

    result = evaluate_translation_brain(
        "good night",
        "es",
        fallback_translation="buenas noches",
        stt_confidence=0.9,
        translation_confidence=0.9,
        context=context,
        speaker_context={"history": ["yes", "ok", "no"], "turns": 9},
    )

    assert result["analysis"]["speaker_style"]["clarity_preference"] >= 0.75
    assert result["response_plan"]["avoid_idioms"] is True


def test_python_brain_auto_repairs_source_language_mismatch_when_translation_is_clean():
    result = evaluate_translation_brain(
        "hola necesito ayuda",
        "en",
        source_language="en",
        fallback_translation="hello I need help",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert result["analysis"]["language"]["detected"] == "es"
    assert result["analysis"]["language_repair_status"]["mode"] == "auto_switch"
    assert result["decision"]["type"] == "response"
    assert result["translated"] == "hello I need help"
    assert result["response_plan"]["strategy"] == "language_auto_repair"
    assert result["response_plan"]["suggested_source_language"] == "es"
    assert result["response_plan"]["client_hints"]["auto_switch_source_language"] is True
    assert result["response_plan"]["client_hints"]["ask_before_speaking"] is False
    assert result["response_plan"]["client_hints"]["language_auto_repaired"] is True
    assert result["response_plan"]["client_hints"]["repaired_source_language"] == "es"
    assert result["response_plan"]["turn_policy"]["mode"] == "instant_translate"
    assert any(option["type"] == "auto_switch_source_language" and option["language"] == "es" for option in result["response_plan"]["repair_options"])


def test_python_brain_detects_informal_register():
    from backend.communication_brain import analyze_communication, detect_register

    assert detect_register("yeah nah mate") == "informal"
    analysis = analyze_communication("yeah I'm gonna head out")
    assert analysis.get("register") == "informal"


def test_python_brain_placeholder_language_mismatch_uses_repair_prompt():
    result = evaluate_translation_brain(
        "hola necesito ayuda",
        "en",
        source_language="en",
        fallback_translation="[en->en] hola necesito ayuda",
        stt_confidence=0.9,
        translation_confidence=0.2,
    )

    assert result["decision"]["reason"] == "placeholder_translation_language_mismatch"
    assert "switch languages" in result["decision"]["message"]


def test_python_brain_does_not_auto_repair_strict_domain_language_mismatch():
    result = evaluate_translation_brain(
        "hola necesito doctor",
        "en",
        source_language="en",
        fallback_translation="hello I need doctor",
        stt_confidence=0.95,
        translation_confidence=0.95,
    )

    assert "medical" in result["analysis"]["domains"]["high_stakes"]
    assert result["analysis"]["language_repair_status"]["mode"] == "confirm_switch"
    assert result["analysis"]["language_repair_status"]["auto_switch"] is False
    assert "strict_domain" in result["analysis"]["language_repair_status"]["blockers"]
    assert result["decision"]["type"] == "clarification"
    assert result["response_plan"]["client_hints"]["auto_switch_source_language"] is False
    assert result["response_plan"]["client_hints"]["suggest_source_language_switch"] is True
    assert result["response_plan"]["client_hints"]["language_auto_repaired"] is False


def test_python_brain_detects_code_switching_without_blocking_good_translation():
    result = evaluate_translation_brain(
        "hello hola",
        "es",
        source_language="en",
        fallback_translation="hola hola",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert result["analysis"]["language"]["code_switching"] is True
    assert "code_switching" in result["analysis"]["quality_flags"]
    assert result["decision"]["type"] == "response"


def test_python_brain_protects_names_and_numbers():
    result = evaluate_translation_brain(
        "Maria is in room 204",
        "es",
        source_language="en",
        fallback_translation="ella esta en la habitacion",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert "missing_protected_terms" in result["analysis"]["quality_flags"]
    assert result["decision"]["reason"] == "missing_protected_terms"
    assert "Maria" in result["response_plan"]["preserve_terms"]
    assert "204" in result["response_plan"]["preserve_terms"]
    repeat_options = [option for option in result["response_plan"]["repair_options"] if option["type"] == "repeat_terms"]
    assert repeat_options
    assert "Maria" in repeat_options[0]["terms"]
    assert "204" in repeat_options[0]["terms"]
    assert result["response_plan"]["conversation_contract"]["preserve_names_numbers_codes"] is True


def test_python_brain_does_not_treat_haitian_common_phrase_as_name():
    result = evaluate_translation_brain(
        "Mesi anpil",
        "ru",
        source_language="ht",
        fallback_translation="Большое спасибо.",
        stt_confidence=0.9,
        translation_confidence=0.9,
    )

    assert result["analysis"]["protected_terms"]["all"] == []
    assert "missing_protected_terms" not in result["analysis"]["quality_flags"]
    assert result["decision"]["type"] == "response"
    assert result["response_plan"]["speak"] is True


def test_python_brain_placeholder_with_protected_terms_uses_precision_prompt():
    result = evaluate_translation_brain(
        "Maria is in room 204",
        "es",
        source_language="en",
        fallback_translation="[en->es] Maria is in room 204",
        stt_confidence=0.9,
        translation_confidence=0.2,
    )

    assert result["decision"]["reason"] == "placeholder_translation_precision"
    assert "Maria" in result["response_plan"]["preserve_terms"]


def test_python_brain_builds_active_speaker_turn_policy():
    result = evaluate_translation_brain(
        "good morning",
        "es",
        source_language="en",
        fallback_translation="buenos dias",
        stt_confidence=0.95,
        translation_confidence=0.95,
        semantic_context={
            "recent_turns": [
                {"speaker": "A", "intent": "statement", "tone": "neutral", "topics": ["hotel"]},
                {"speaker": "B", "intent": "statement", "tone": "neutral", "topics": ["morning"]},
            ],
        },
    )

    turn_policy = result["response_plan"]["turn_policy"]
    assert turn_policy["active_speaker"] == "B"
    assert turn_policy["previous_speaker"] == "A"
    assert turn_policy["speaker_shift"] is True
    assert turn_policy["interruption_policy"] == "allow_shift"
    assert turn_policy["mode"] == "instant_translate"
    assert result["response_plan"]["client_hints"]["active_speaker"] == "B"
