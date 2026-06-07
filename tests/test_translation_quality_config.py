"""Config knobs for translation quality benchmarking (Phase 2)."""

import os

import pytest

from backend.config import get_nllb_model, get_translation_num_beams


def test_translation_num_beams_default():
    os.environ.pop("TRANSLATION_NUM_BEAMS", None)
    os.environ.pop("TRANSLATION_QUALITY_NUM_BEAMS", None)
    assert get_translation_num_beams(quality=False) == 1
    assert get_translation_num_beams(quality=True) == 4


def test_translation_num_beams_env_override(monkeypatch):
    monkeypatch.setenv("TRANSLATION_NUM_BEAMS", "2")
    monkeypatch.setenv("TRANSLATION_QUALITY_NUM_BEAMS", "6")
    assert get_translation_num_beams(quality=False) == 2
    assert get_translation_num_beams(quality=True) == 6


def test_nllb_model_default(monkeypatch):
    monkeypatch.delenv("NLLB_MODEL", raising=False)
    assert get_nllb_model() == "facebook/nllb-200-distilled-600M"


def test_nllb_model_override(monkeypatch):
    monkeypatch.setenv("NLLB_MODEL", "facebook/nllb-200-1.3B")
    assert get_nllb_model() == "facebook/nllb-200-1.3B"


def test_api_translation_quality_flag():
    from backend.api import _translation_wants_quality

    assert _translation_wants_quality("accurate", None) is True
    assert _translation_wants_quality(None, "quality") is True
    assert _translation_wants_quality("fast", "fast") is False
