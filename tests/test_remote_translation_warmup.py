from translation.remote_translator import RemoteTranslator


def test_remote_translation_warmup_pairs_cover_all_targets():
    from backend.api import REMOTE_TRANSLATION_WARMUP_TEXTS, _CONFIGURED_LANGUAGE_CODES

    targets = {target for _, target, _ in REMOTE_TRANSLATION_WARMUP_TEXTS}
    assert set(_CONFIGURED_LANGUAGE_CODES) - {"en"} <= targets


def test_remote_translation_warmup_includes_emergency_phrases():
    from backend.api import REMOTE_TRANSLATION_WARMUP_TEXTS

    emergency = {
        (source, target, text)
        for source, target, text in REMOTE_TRANSLATION_WARMUP_TEXTS
        if text in {"Help", "I need a doctor", "Call the police"}
    }
    assert len(emergency) >= 39


def test_remote_translator_caches_repeated_requests(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(request.full_url)

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'[[["hola"]]]'

        return _Resp()

    monkeypatch.setattr("translation.remote_translator.urlopen", fake_urlopen)
    translator = RemoteTranslator(timeout_seconds=2)
    first = translator.translate("hello", "en", "es")
    second = translator.translate("hello", "en", "es")

    assert first == "hola"
    assert second == "hola"
    assert len(calls) == 1


def test_remote_translator_retries_once_on_failure(monkeypatch):
    calls = []

    def flaky_urlopen(request, timeout=None):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("temporary timeout")

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'[[["hola"]]]'

        return _Resp()

    monkeypatch.setattr("translation.remote_translator.urlopen", flaky_urlopen)
    translator = RemoteTranslator(timeout_seconds=2)
    assert translator.translate("hello", "en", "es") == "hola"
    assert len(calls) == 2
