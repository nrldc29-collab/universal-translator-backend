from tts.tts_readiness import is_edge_tts_importable, neural_tts_status


def test_neural_tts_status_shape():
    status = neural_tts_status()
    assert "neural_ready" in status
    assert "edge_tts" in status
    assert "ffmpeg" in status
    assert isinstance(status["issues"], list)


def test_edge_importable_after_install():
    assert is_edge_tts_importable() is True
