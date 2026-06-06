from translation.lightweight_translator import LightweightTranslator


def test_english_hello_has_instant_translation_for_configured_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        translated = translator.translate("Hello", "en", target)
        assert translated
        assert not translated.startswith(f"[en->{target}]")
        assert "AI:" not in translated
        assert "Keep meaning:" not in translated


def test_configured_source_greetings_have_instant_translation_to_english():
    translator = LightweightTranslator()
    greetings = {
        "es": "Hola",
        "fr": "Bonjour",
        "de": "Hallo",
        "it": "Ciao",
        "pt": "Olá",
        "nl": "Hallo",
        "ru": "\u041f\u0440\u0438\u0432\u0435\u0442",
        "zh": "\u4f60\u597d",
        "ja": "\u3053\u3093\u306b\u3061\u306f",
        "ko": "\uc548\ub155\ud558\uc138\uc694",
        "ar": "\u0645\u0631\u062d\u0628\u0627",
        "hi": "\u0928\u092e\u0938\u094d\u0924\u0947",
        "ht": "Bonjou",
    }

    for source, greeting in greetings.items():
        translated = translator.translate(greeting, source, "en")
        assert translated
        assert not translated.startswith(f"[{source}->en]")
        assert translated.lower().startswith("hello")
