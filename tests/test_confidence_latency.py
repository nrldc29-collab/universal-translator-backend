"""Tests for backend.confidence and backend.latency modules."""

from backend.confidence import (
    ConfidenceEngine,
    assess_translation_confidence,
    estimate_stt_confidence,
    estimate_translation_confidence,
    is_placeholder_translation,
    detect_ambiguities,
    ambiguity_score,
    clarification_for,
)
from backend.latency import LatencyEngine


# ---------------------------------------------------------------------------
# ConfidenceEngine
# ---------------------------------------------------------------------------

class TestConfidenceEngine:
    def test_perfect_scores_return_near_one(self):
        engine = ConfidenceEngine()
        score = engine.evaluate(1.0, 1.0, 0.0, 1.0)
        assert score > 0.95

    def test_zero_scores_return_near_zero(self):
        engine = ConfidenceEngine()
        score = engine.evaluate(0.0, 0.0, 1.0, 0.0)
        assert score < 0.15

    def test_score_is_clamped_to_0_1(self):
        engine = ConfidenceEngine()
        assert 0.0 <= engine.evaluate(2.0, 2.0, -1.0, 2.0) <= 1.0
        assert 0.0 <= engine.evaluate(-1.0, -1.0, 2.0, -1.0) <= 1.0

    def test_high_ambiguity_lowers_score(self):
        engine = ConfidenceEngine()
        low = engine.evaluate(0.8, 0.8, 1.0, 0.6)
        high = engine.evaluate(0.8, 0.8, 0.0, 0.6)
        assert high > low


# ---------------------------------------------------------------------------
# estimate_stt_confidence
# ---------------------------------------------------------------------------

class TestEstimateSttConfidence:
    def test_empty_returns_zero(self):
        assert estimate_stt_confidence("") == 0.0
        assert estimate_stt_confidence("   ") == 0.0

    def test_single_word_returns_moderate_without_acoustic(self):
        assert estimate_stt_confidence("hello") == 0.42

    def test_acoustic_confidence_boosts_short_utterances(self):
        score = estimate_stt_confidence("yes", acoustic_confidence=0.9)
        assert score >= 0.75

    def test_medium_sentence_returns_moderate(self):
        score = estimate_stt_confidence("hello how are you")
        assert 0.5 <= score <= 0.82

    def test_long_sentence_returns_high(self):
        assert estimate_stt_confidence("the quick brown fox jumps over the lazy dog") == 0.84


# ---------------------------------------------------------------------------
# estimate_translation_confidence
# ---------------------------------------------------------------------------

class TestEstimateTranslationConfidence:
    def test_cross_script_translation_does_not_compare_words_to_characters(self):
        assert estimate_translation_confidence("Hello", "\u3053\u3093\u306b\u3061\u306f\u3002") >= 0.65

    def test_missing_cjk_name_lowers_confidence(self):
        with_name = estimate_translation_confidence("Dr. Chen went to the clinic.", "El Dr. Chen fue a la clínica.")
        without_name = estimate_translation_confidence("Dr. Chen went to the clinic.", "El doctor fue a la clínica.")
        assert with_name > without_name

    def test_empty_translation_returns_zero(self):
        assert estimate_translation_confidence("hello", "") == 0.0

    def test_placeholder_returns_low(self):
        score = estimate_translation_confidence("hello", "[en->es] hello")
        assert score == 0.22

    def test_identical_source_target_returns_moderate(self):
        score = estimate_translation_confidence("hello", "hello")
        assert score == 0.45

    def test_reasonable_translation_returns_high(self):
        score = estimate_translation_confidence("hello world", "hola mundo")
        assert score > 0.6

    def test_extreme_length_ratio_returns_moderate(self):
        score = estimate_translation_confidence("hi", "this is a very very very very long translation")
        assert score < 0.7

    def test_missing_proper_nouns_lowers_confidence(self):
        with_name = estimate_translation_confidence("Meet Marie at CVS.", "Rencontrez Marie à CVS.")
        without_name = estimate_translation_confidence("Meet Marie at CVS.", "Rencontrez-les là-bas.")
        assert with_name > without_name


# ---------------------------------------------------------------------------
# is_placeholder_translation
# ---------------------------------------------------------------------------

class TestIsPlaceholderTranslation:
    def test_detects_placeholder(self):
        assert is_placeholder_translation("[en->es] hello") is True
        assert is_placeholder_translation("[FR->DE] bonjour") is True

    def test_real_translation_not_placeholder(self):
        assert is_placeholder_translation("hola mundo") is False
        assert is_placeholder_translation("") is False


# ---------------------------------------------------------------------------
# detect_ambiguities / ambiguity_score / clarification_for
# ---------------------------------------------------------------------------

class TestAmbiguity:
    def test_detects_known_ambiguous_words(self):
        result = detect_ambiguities("I went to the bank")
        assert "bank" in result

    def test_no_ambiguities_in_clear_text(self):
        result = detect_ambiguities("I love programming")
        assert result == []

    def test_whole_word_matching_only(self):
        result = detect_ambiguities("banker bankroll")
        assert "bank" not in result

    def test_ambiguity_score_increases_with_ambiguous_words(self):
        score_none = ambiguity_score("I love programming")
        score_one = ambiguity_score("I went to the bank")
        score_multi = ambiguity_score("bank right fine charge")
        assert score_none < score_one < score_multi

    def test_ambiguity_score_capped_at_one(self):
        assert ambiguity_score("bank right fine charge match set run case") <= 1.0

    def test_clarification_for_known_word_includes_senses(self):
        msg = clarification_for("go to the bank", ["bank"])
        assert "bank" in msg
        assert "money" in msg or "river" in msg

    def test_clarification_for_no_ambiguities_returns_generic(self):
        msg = clarification_for("hello", [])
        assert "rephrase" in msg.lower() or "misunderstood" in msg.lower()

    def test_detects_spanish_ambiguity(self):
        result = detect_ambiguities("fui al banco", source_lang="es")
        assert "banco" in result

    def test_detects_french_ambiguity(self):
        result = detect_ambiguities("je vais à la banque", source_lang="fr")
        assert "banque" in result

    def test_cjk_heuristic_stt_confidence_uses_length_units(self):
        from backend.confidence import _heuristic_stt_confidence

        short_cjk = _heuristic_stt_confidence("你好")
        longer_cjk = _heuristic_stt_confidence("你好世界今天天气很好")
        assert short_cjk < longer_cjk

    def test_assess_uses_source_language_ambiguity(self):
        es = assess_translation_confidence(
            "fui al banco",
            "I went to the bench",
            source_language="es",
        )
        en = assess_translation_confidence(
            "fui al banco",
            "I went to the bench",
            source_language="en",
        )
        assert es.get("confidence", 1.0) <= en.get("confidence", 1.0)


class TestNativeSpeakerCertification:
    def test_clear_short_text_without_measured_audio_is_not_blocked(self):
        assessed = assess_translation_confidence("Hello", "Hola")

        assert assessed["low_confidence"] is False
        assert assessed["needs_native_certification"] is False
        assert assessed["human_certification_step"] == "none"

    def test_informal_register_recommends_native_listen(self):
        from backend.confidence import subjective_accent_tone_signals

        subj = subjective_accent_tone_signals(register="informal", tone="neutral", emotion="neutral")
        assert subj["subjective"] is True
        assert "informal_register" in subj["signals"]

    def test_high_confidence_informal_does_not_require_certification_block(self):
        assessed = assess_translation_confidence(
            "yeah I'm gonna head out",
            "sí, me voy",
            stt_confidence=0.92,
            register="informal",
            tone="neutral",
            context_match=0.8,
        )
        assert assessed["native_speaker_listen_recommended"] is True
        assert assessed["needs_native_certification"] is False
        assert assessed["human_certification_step"] == "advisory"
        assert assessed["certification_message"]

    def test_weak_acoustic_informal_requires_certification(self):
        assessed = assess_translation_confidence(
            "yeah I'm gonna head out",
            "sí, me voy",
            stt_confidence=0.5,
            acoustic_confidence=0.4,
            register="informal",
            tone="emphatic",
            context_match=0.7,
        )
        assert assessed["needs_native_certification"] is True
        assert assessed["human_certification_step"] == "required"

    def test_low_confidence_informal_requires_certification(self):
        assessed = assess_translation_confidence(
            "yeah",
            "[en->es] yeah",
            register="informal",
            stt_confidence=0.4,
            context_match=0.5,
        )
        assert assessed["needs_native_certification"] is True


class TestAssessTranslationConfidence:
    def test_high_stakes_lowers_threshold(self):
        assessment = assess_translation_confidence(
            "I need a doctor for chest pain",
            "Necesito un doctor por dolor de pecho",
            domains={"high_stakes": ["medical"], "risk_level": "high"},
        )
        assert assessment["high_stakes"] == ["medical"]
        assert assessment["confidence_threshold"] >= 0.78

    def test_low_confidence_sets_message(self):
        assessment = assess_translation_confidence(
            "bank",
            "[en->es] bank",
            domains={"high_stakes": ["financial"], "risk_level": "high"},
        )
        assert assessment["low_confidence"] is True
        assert assessment["confidence_message"]

    def test_weak_context_match_lowers_confidence(self):
        strong = assess_translation_confidence(
            "I need help at the hospital",
            "Necesito ayuda en el hospital",
            context_match=0.85,
        )
        weak = assess_translation_confidence(
            "I need help at the hospital",
            "Necesito ayuda en el hospital",
            context_match=0.25,
        )
        assert strong["confidence"] > weak["confidence"]

    def test_cjk_length_ratio_uses_characters(self):
        score = estimate_translation_confidence("我需要帮助", "I need help")
        assert score > 0.5


# ---------------------------------------------------------------------------
# LatencyEngine
# ---------------------------------------------------------------------------

class TestLatencyEngine:
    def test_initial_total_is_zero(self):
        engine = LatencyEngine()
        assert engine.total() == 0.0

    def test_single_update_applies_ewma(self):
        engine = LatencyEngine()
        engine.update(stt=100.0)
        assert 0.0 < engine.avg_stt < 100.0

    def test_repeated_same_value_converges(self):
        engine = LatencyEngine()
        for _ in range(50):
            engine.update(stt=200.0, translate=100.0, tts=50.0)
        assert abs(engine.avg_stt - 200.0) < 5.0
        assert abs(engine.avg_translate - 100.0) < 5.0
        assert abs(engine.avg_tts - 50.0) < 5.0

    def test_total_sums_all_averages(self):
        engine = LatencyEngine()
        for _ in range(50):
            engine.update(stt=100.0, translate=100.0, tts=100.0)
        assert abs(engine.total() - 300.0) < 15.0

    def test_update_accepts_int_values(self):
        engine = LatencyEngine()
        engine.update(stt=100, translate=50, tts=25)
        assert engine.avg_stt > 0
