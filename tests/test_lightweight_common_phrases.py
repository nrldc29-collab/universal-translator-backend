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


def test_english_conversation_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("yes", "please", "i don't understand"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} for {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_barrier_phrases_translate_without_english_pivot():
    translator = LightweightTranslator()
    pairs = (
        ("bonjou", "ht", "es", "hola"),
        ("hola", "es", "ht", "bonjou"),
        ("bonjou", "ht", "fr", "bonjour"),
        ("bonjour", "fr", "ht", "bonjou"),
        ("hola", "es", "fr", "bonjour"),
        ("hallo", "de", "fr", "bonjour"),
        ("bonjour", "fr", "de", "hallo"),
        ("hola", "es", "de", "hallo"),
        ("ciao", "it", "fr", "bonjour"),
        ("hola", "es", "pt", "olá"),
        ("ola", "pt", "fr", "bonjour"),
    )
    for phrase, source, target, expected_start in pairs:
        translated = translator.translate(phrase, source, target).lower()
        assert translated, f"missing {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        assert translated.startswith(expected_start)


def test_english_pivot_builds_cross_language_phrases():
    translator = LightweightTranslator()
    pairs = (
        ("hola", "es", "fr", "bonjour"),
        ("gracias", "es", "de", "danke"),
        ("ciao", "it", "pt", "olá"),
        ("mesi", "ht", "es", "gracias"),
        ("gracias", "es", "ja", "ありがとう"),
        ("tanpri", "ht", "fr", "s'il"),
        ("wi", "ht", "de", "ja"),
    )
    for phrase, source, target, expected_start in pairs:
        translated = translator.translate(phrase, source, target).lower()
        assert translated, f"missing pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        assert translated.startswith(expected_start)


def test_native_help_phrases_translate_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("j ai besoin d aide", "fr", "es", "necesito"),
        ("ich brauche hilfe", "de", "ht", "mwen"),
        ("ho bisogno di aiuto", "it", "fr", "j'ai"),
        ("preciso de ajuda", "pt", "de", "ich"),
        ("ik heb hulp nodig", "nl", "en", "i need"),
        ("mwen bezwen ed", "ht", "ja", "助"),
    )
    for phrase, source, target, expected_start in pairs:
        translated = translator.translate(phrase, source, target).lower()
        assert translated, f"missing {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        assert translated.startswith(expected_start)


def test_life_context_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("i am a student", "i am tired", "my wife", "it is raining", "do you have wifi", "where is the atm"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} life {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_life_context_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("mwen fatige", "ht", "es", "cansad"),
        ("soy estudiante", "es", "fr", "tudiant"),
        ("ich habe kein geld", "de", "it", "soldi"),
        ("ihavenomoney", "en", "ja", "お金"),
    )
    for phrase, source, target, expected in pairs:
        translated = translator.translate(phrase, source, target)
        assert translated, f"missing life pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        if expected.isascii():
            assert expected in translated.lower()
        else:
            assert expected in translated


def test_courtesy_safety_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("good evening", "i am sorry", "you are welcome", "it hurts here", "where is the embassy"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} courtesy {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_courtesy_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("buenas noches", "es", "fr", "bonsoir"),
        ("bon swa", "ht", "es", "noche"),
        ("lo siento", "es", "de", "leid"),
        ("ithurtshere", "en", "ja", "痛"),
    )
    for phrase, source, target, expected in pairs:
        translated = translator.translate(phrase, source, target)
        assert translated, f"missing courtesy pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        if expected.isascii():
            assert expected in translated.lower()
        else:
            assert expected in translated


def test_number_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("1", "one", "five", "10", "ten", "twenty"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} number {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_number_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("uno", "es", "fr", "un"),
        ("youn", "ht", "es", "uno"),
        ("drei", "de", "it", "tre"),
        ("5", "en", "zh", "五"),
    )
    for phrase, source, target, expected in pairs:
        translated = translator.translate(phrase, source, target)
        assert translated, f"missing number pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        assert expected in translated


def test_essential_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("i dont know", "i understand", "speak slowly", "i lost my passport", "i need medicine"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} essential {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_daily_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("today", "tomorrow", "i have a reservation", "how much is this", "see you later"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} daily {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_daily_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("hoy", "es", "fr", "aujourd"),
        ("demen", "ht", "es", "ana"),
        ("heute", "de", "it", "oggi"),
        ("howmuchisthis", "en", "ja", "くら"),
    )
    for phrase, source, target, expected in pairs:
        translated = translator.translate(phrase, source, target)
        assert translated, f"missing daily pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        if expected.isascii():
            assert expected in translated.lower()
        else:
            assert expected in translated


def test_food_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("i am hungry", "the check please", "i am vegetarian", "no spicy please"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} food {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_medical_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("i feel sick", "i have a fever", "call an ambulance"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} medical {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_food_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("tengo hambre", "es", "fr", "faim"),
        ("mwen grangou", "ht", "es", "hambre"),
        ("ich habe hunger", "de", "it", "fame"),
        ("iamhungry", "en", "ja", "すき"),
    )
    for phrase, source, target, expected in pairs:
        translated = translator.translate(phrase, source, target)
        assert translated, f"missing food pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        if expected.isascii():
            assert expected in translated.lower()
        else:
            assert expected in translated


def test_direction_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("turn left", "go straight", "i need a taxi", "where is the bus stop"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} direction {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_direction_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("gire a la izquierda", "es", "fr", "tournez"),
        ("vire a goch", "ht", "es", "gire"),
        ("biegen sie links ab", "de", "it", "sinistra"),
        ("turnleft", "en", "ja", "左"),
    )
    for phrase, source, target, expected in pairs:
        translated = translator.translate(phrase, source, target)
        assert translated, f"missing direction pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        if expected.isascii():
            assert expected in translated.lower()
        else:
            assert expected in translated


def test_travel_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("do you speak english", "where is the pharmacy", "water please"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} travel {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_travel_phrases_pivot_across_languages():
    translator = LightweightTranslator()
    pairs = (
        ("habla ingles", "es", "fr", "parlez"),
        ("eske ou pale angle", "ht", "es", "habla"),
        ("mwen pa pale angle", "ht", "de", "ich"),
        ("parlez vous anglais", "fr", "es", "habla"),
    )
    for phrase, source, target, expected_start in pairs:
        translated = translator.translate(phrase, source, target).lower()
        assert translated, f"missing travel pivot {source}->{target} for {phrase!r}"
        assert not translated.startswith(f"[{source}->{target}]")
        assert expected_start in translated


def test_emergency_phrases_translate_for_all_targets():
    translator = LightweightTranslator()
    targets = ["es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht"]

    for target in targets:
        for phrase in ("help", "i need a doctor", "call the police", "where is the hospital"):
            translated = translator.translate(phrase, "en", target)
            assert translated, f"missing en->{target} emergency {phrase!r}"
            assert not translated.startswith(f"[en->{target}]")


def test_phrase_aliases_handle_stt_spacing_variants():
    translator = LightweightTranslator()
    assert translator.translate("thankyou", "en", "es").lower().startswith("grac")
    assert translator.translate("buenos dias", "es", "fr").lower().startswith("bon")


def test_haitian_creole_conversation_phrases_translate_to_english():
    translator = LightweightTranslator()
    for phrase, expected_start in (
        ("wi", "yes"),
        ("tanpri", "please"),
        ("mwen pa konprann", "i don't"),
    ):
        translated = translator.translate(phrase, "ht", "en").lower()
        assert translated.startswith(expected_start)
