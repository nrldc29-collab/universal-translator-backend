"""Tests for backend.tts_pacing - emotion detection and TTS prosody."""
import pytest
from backend.tts_pacing import (
    EmotionType,
    ProsodyFeatures,
    TTS_STYLE_MAP_ADVANCED,
    build_tts_pacing,
    detect_emotion_advanced,
    detect_urgency_advanced,
)


class TestProsodyFeatures:
    def test_clamps_pitch_to_range(self):
        pf = ProsodyFeatures(pitch=10.0)
        assert pf.pitch == 2.0

    def test_clamps_speed_minimum(self):
        pf = ProsodyFeatures(speed=0.0)
        assert pf.speed == 0.5

    def test_to_dict_has_required_keys(self):
        pf = ProsodyFeatures()
        d = pf.to_dict()
        assert "pitch" in d
        assert "speed" in d
        assert "energy" in d


class TestDetectEmotionAdvanced:
    def test_neutral_on_plain_text(self):
        emotion, _ = detect_emotion_advanced("The meeting is at 3pm")
        assert emotion == EmotionType.NEUTRAL

    def test_detects_happy(self):
        emotion, confidence = detect_emotion_advanced("I am so happy and delighted to see you")
        assert emotion == EmotionType.HAPPY
        assert confidence > 0

    def test_detects_apologetic(self):
        emotion, _ = detect_emotion_advanced("I'm so sorry for the trouble")
        assert emotion == EmotionType.APOLOGETIC

    def test_detects_angry(self):
        emotion, _ = detect_emotion_advanced("This is outrageous and stupid")
        assert emotion == EmotionType.ANGRY

    def test_intent_question_boosts_curious(self):
        emotion, _ = detect_emotion_advanced("The weather", intent="question")
        assert emotion == EmotionType.CURIOUS

    def test_returns_tuple_of_two(self):
        result = detect_emotion_advanced("hello")
        assert len(result) == 2


class TestDetectUrgencyAdvanced:
    def test_low_urgency_on_plain_text(self):
        assert detect_urgency_advanced("The weather is nice") == "low"

    def test_high_urgency_emergency_keyword(self):
        assert detect_urgency_advanced("This is an emergency!") == "high"

    def test_high_urgency_help_keyword(self):
        assert detect_urgency_advanced("Help me please") == "high"

    def test_medium_urgency_on_please(self):
        assert detect_urgency_advanced("Please review this soon") == "medium"

    def test_medium_urgency_from_intent(self):
        assert detect_urgency_advanced("Do that", intent="instruction") == "medium"

    def test_high_urgency_from_angry_emotion(self):
        assert detect_urgency_advanced("", emotion=EmotionType.ANGRY) == "high"


class TestTtsStyleMap:
    def test_all_emotions_have_style(self):
        for emotion in EmotionType:
            assert emotion in TTS_STYLE_MAP_ADVANCED

    def test_neutral_is_baseline(self):
        neutral = TTS_STYLE_MAP_ADVANCED[EmotionType.NEUTRAL]
        assert neutral.pitch == 1.0
        assert neutral.speed == 1.0


class TestBuildTtsPacing:
    def test_returns_dict(self):
        result = build_tts_pacing("Hello there", {})
        assert isinstance(result, dict)

    def test_has_emotion_key(self):
        result = build_tts_pacing("Hello there", {})
        assert "emotion" in result

    def test_emergency_triggers_high_urgency(self):
        result = build_tts_pacing("Emergency! Call 911 immediately!", {})
        assert result.get("urgency") == "high"
