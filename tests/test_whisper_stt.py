from speech.whisper_stt import WhisperSpeechToText, build_initial_prompt, normalize_transcript


class _Segment:
    def __init__(self, text):
        self.text = text


class _RecordingModel:
    def __init__(self, text):
        self.text = text
        self.options = None

    def transcribe(self, _audio_path, **options):
        self.options = options
        return [_Segment(self.text)], None


def test_build_initial_prompt_merges_language_seed_and_live_text():
    prompt = build_initial_prompt("ht", "mwen bezwen")
    assert "mwen" in prompt
    assert "bezwen" in prompt
    assert len(prompt) <= 240


def test_haitian_transcription_uses_language_hints_and_normalizes_phonetics():
    model = _RecordingModel("Moen besuane yondokte.")
    stt = WhisperSpeechToText()

    result = stt._run_transcribe(model, "sample.wav", "ht")

    assert result.text == "Mwen bezwen yon dokte."
    assert model.options["language"] == "ht"
    assert model.options["beam_size"] >= 2
    assert model.options["vad_filter"] is True
    assert "initial_prompt" in model.options
    assert model.options["initial_prompt"]
    assert "hotwords" not in model.options


def test_haitian_phonetic_cleanup_covers_observed_field_failures():
    assert normalize_transcript("Mesi empil pwedu.", "ht") == "Mèsi anpil pou ed ou."
    assert normalize_transcript("Mesi anpil poedu.", "ht") == "Mèsi anpil pou ed ou."
    assert normalize_transcript("Mesi anpil pu\u00e9du.", "ht") == "Mèsi anpil pou ed ou."
    assert normalize_transcript("mwen bezwen yandokte", "ht") == "mwen bezwen yon dokte"
    assert normalize_transcript("Moin besoin yon dokte.", "ht") == "Mwen bezwen yon dokte."
    assert normalize_transcript("Mouin pa konprann", "ht") == "Mwen pa konprann"
    assert normalize_transcript("Mu en pa kontran.", "ht") == "Mwen pa konprann."


def test_transcript_cleanup_does_not_rewrite_other_languages():
    original = "Moen besuane yondokte."
    assert normalize_transcript(original, "fr") == original


def test_russian_phonetic_cleanup():
    assert normalize_transcript("пожалуста", "ru") == "пожалуйста"


def test_chinese_phonetic_cleanup():
    assert normalize_transcript("在那里", "zh") == "在哪里"
