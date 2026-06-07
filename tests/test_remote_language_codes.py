from translation.remote_translator import REMOTE_LANGUAGE_CODES, _remote_language


def test_all_app_languages_have_remote_codes():
    expected = {"en", "es", "ht", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi"}
    assert set(REMOTE_LANGUAGE_CODES) == expected


def test_remote_language_normalizes_region_codes():
    assert _remote_language("zh-CN") == "zh-CN"
    assert _remote_language("pt-BR") == "pt"
    assert _remote_language("HT") == "ht"
