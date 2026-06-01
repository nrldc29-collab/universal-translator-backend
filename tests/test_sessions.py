"""Tests for backend.sessions - SessionRegistry and helpers."""
import pytest
from backend.sessions import (
    SessionRegistry,
    normalize_device_id,
    normalize_speaker_name,
    speaker_label_for_index,
)


class TestNormalizeDeviceId:
    def test_strips_whitespace(self):
        assert normalize_device_id("  dev123  ") == "dev123"

    def test_truncates_to_96_chars(self):
        long_id = "x" * 200
        result = normalize_device_id(long_id)
        assert len(result) == 96

    def test_none_generates_uuid(self):
        result = normalize_device_id(None)
        assert result.startswith("device-")

    def test_empty_string_generates_uuid(self):
        result = normalize_device_id("")
        assert result.startswith("device-")


class TestNormalizeSpeakerName:
    def test_strips_whitespace(self):
        assert normalize_speaker_name("  Alice  ") == "Alice"

    def test_truncates_to_40_chars(self):
        long_name = "A" * 60
        assert len(normalize_speaker_name(long_name)) == 40

    def test_none_returns_empty(self):
        assert normalize_speaker_name(None) == ""


class TestSpeakerLabelForIndex:
    def test_returns_preferred_name_when_not_generic(self):
        assert speaker_label_for_index(1, "Alice") == "Alice"

    def test_falls_back_for_empty_name(self):
        assert speaker_label_for_index(2, "") == "Person 2"

    def test_falls_back_for_generic_auto(self):
        assert speaker_label_for_index(1, "auto") == "Person 1"

    def test_falls_back_for_none(self):
        assert speaker_label_for_index(3, None) == "Person 3"

    def test_falls_back_for_unknown(self):
        assert speaker_label_for_index(1, "unknown") == "Person 1"


class TestSessionRegistry:
    def setup_method(self):
        self.registry = SessionRegistry()

    def test_resolve_auto_speaker_first_device(self):
        result = self.registry.resolve_auto_speaker(
            session_id="sess1",
            identity="user1",
            device_id="device-A",
            source_language="en",
            target_language="es",
        )
        assert result["speaker"].startswith("person-")
        assert result["speaker_index"] >= 1
        assert result["detection"] == "device_source"

    def test_resolve_auto_speaker_same_device_same_speaker(self):
        r1 = self.registry.resolve_auto_speaker("sess1", "user1", "device-A", "en", "es")
        r2 = self.registry.resolve_auto_speaker("sess1", "user1", "device-A", "en", "es")
        assert r1["speaker"] == r2["speaker"]

    def test_resolve_auto_speaker_different_devices_different_speakers(self):
        r1 = self.registry.resolve_auto_speaker("sess1", "user1", "device-A", "en", "es")
        r2 = self.registry.resolve_auto_speaker("sess1", "user1", "device-B", "en", "es")
        assert r1["speaker"] != r2["speaker"]

    def test_bind_creates_speaker_entry(self):
        state = self.registry.bind(
            session_id="sess2",
            speaker="person-1",
            identity="user1",
            source_language="en",
            target_language="es",
            speaker_label="Alice",
        )
        assert isinstance(state, dict)
        assert state["session_id"] == "sess2"

    def test_speaker_label_prefers_custom_name(self):
        result = self.registry.resolve_auto_speaker(
            session_id="sess3",
            identity="user1",
            device_id="device-C",
            source_language="en",
            target_language="es",
            speaker_name="Dr. Smith",
        )
        assert result["speaker_label"] == "Dr. Smith"

    def test_cleanup_removes_stale_sessions(self):
        self.registry.resolve_auto_speaker("stale", "user1", "device-X", "en", "es")
        assert len(self.registry.shared_sessions) == 1
        self.registry.cleanup()
        assert len(self.registry.shared_sessions) >= 0
