from backend.ailang_pipeline import AILangContext, AILangPipelineManager


def test_offline_agents_use_local_rules_without_loading_bridge(monkeypatch):
    monkeypatch.setenv("USE_LLM_AGENTS", "false")
    manager = AILangPipelineManager()
    context = AILangContext(
        session_id="offline-realtime",
        current_speaker="Person 1",
        conversation_history=[
            {"speaker": "Person 1", "text": "Maria called the clinic.", "translated": ""},
        ],
    )

    def fail_if_bridge_loads():
        raise AssertionError("offline rules must not load a network-backed agent")

    monkeypatch.setattr(manager, "_get_bridge", fail_if_bridge_loads)

    memory = manager.process_context_memory("Please tell her I am here.", "en", context)
    profile = manager.process_speaker_profile("I gotta go now.", "en", "es", context)
    ambiguity = manager.process_ambiguity_resolution("Break a leg.", "en", "es", context)
    confidence = manager.process_confidence_fallback(
        "hello", "hola", 0.5, "en", "es", context, [],
    )
    verification = manager.process_back_translation("hello", "hola", "en", "es", context)
    emotion = manager.process_emotion_tts("I am worried.", "es", context)

    assert memory["method"] == "offline_rules"
    assert profile["method"] == "offline_rules"
    assert ambiguity["has_ambiguities"] is True
    assert confidence["method"] == "offline_rules"
    assert verification["method"] == "offline_rules"
    assert emotion["method"] == "offline_rules"
