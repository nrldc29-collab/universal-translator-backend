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

    def test_single_word_returns_low(self):
        assert estimate_stt_confidence("hello") == 0.28

    def test_medium_sentence_returns_moderate(self):
        score = estimate_stt_confidence("hello how are you")
        assert 0.5 <= score <= 0.82

    def test_long_sentence_returns_high(self):
        assert estimate_stt_confidence("the quick brown fox jumps over the lazy dog") == 0.82


# ---------------------------------------------------------------------------
# estimate_translation_confidence
# ---------------------------------------------------------------------------

class TestEstimateTranslationConfidence:
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
