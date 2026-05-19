from backend.streaming import extract_client_voice_active


def test_extract_client_voice_active_accepts_legacy_key():
    assert extract_client_voice_active({"voice_active": True}) is True


def test_extract_client_voice_active_accepts_explicit_key():
    assert extract_client_voice_active({"client_voice_active": True}) is True


def test_extract_client_voice_active_prefers_legacy_key_when_present():
    assert extract_client_voice_active({"voice_active": False, "client_voice_active": True}) is False
