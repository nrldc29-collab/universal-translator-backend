from functools import lru_cache

import gradio as gr
from faster_whisper import WhisperModel
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


LANGUAGES = {
    "en": "English",
    "ht": "Haitian Creole",
}

NLLB_MODEL = "facebook/nllb-200-distilled-600M"
NLLB_LANG = {
    "en": "eng_Latn",
    "ht": "hat_Latn",
}


@lru_cache(maxsize=1)
def load_whisper() -> WhisperModel:
    return WhisperModel("tiny", device="cpu", compute_type="int8")


@lru_cache(maxsize=1)
def load_translation_model():
    tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL)
    return tokenizer, model


def transcribe_audio(audio_input, source_language: str = "en") -> tuple[str, str]:
    if audio_input is None:
        return "", ""

    whisper_language = None if source_language in ("", "auto") else source_language
    segments, info = load_whisper().transcribe(
        audio_input,
        language=whisper_language,
        beam_size=1,
        vad_filter=True,
    )
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    detected = getattr(info, "language", "") or source_language or "en"
    return transcript, detected


def translate_text(text: str, source_language: str = "en", target_language: str = "ht") -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if source_language == target_language:
        return text
    if source_language not in NLLB_LANG or target_language not in NLLB_LANG:
        raise ValueError("This Space demo supports English <-> Haitian Creole.")

    tokenizer, model = load_translation_model()
    tokenizer.src_lang = NLLB_LANG[source_language]
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(NLLB_LANG[target_language])
    generate_kwargs = {"max_new_tokens": 256}
    if isinstance(forced_bos_token_id, int) and forced_bos_token_id >= 0:
        generate_kwargs["forced_bos_token_id"] = forced_bos_token_id
    outputs = model.generate(**inputs, **generate_kwargs)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def transcribe_and_translate(audio_input, source_language: str, target_language: str):
    transcript, detected_language = transcribe_audio(audio_input, source_language)
    if not transcript:
        return "", detected_language, ""
    active_source = detected_language if detected_language in NLLB_LANG else source_language
    translation = translate_text(transcript, active_source, target_language)
    return transcript, detected_language, translation


def language_choices():
    return [(name, code) for code, name in LANGUAGES.items()]


with gr.Blocks(title="Anai Translator") as demo:
    gr.Markdown("# Anai Translator")
    gr.Markdown("Record or upload speech, transcribe it, and translate between English and Haitian Creole.")

    with gr.Tab("Audio Translation"):
        with gr.Row():
            source_audio_language = gr.Dropdown(
                choices=language_choices(),
                value="en",
                label="Source language",
            )
            target_audio_language = gr.Dropdown(
                choices=language_choices(),
                value="ht",
                label="Target language",
            )

        audio_input = gr.Audio(
            label="Record or upload audio",
            type="filepath",
            sources=["microphone", "upload"],
        )
        translate_audio_button = gr.Button("Transcribe and translate", variant="primary")

        transcript_output = gr.Textbox(label="Transcript", lines=4)
        detected_language_output = gr.Textbox(label="Detected language")
        audio_translation_output = gr.Textbox(label="Translation", lines=4)

        translate_audio_button.click(
            fn=transcribe_and_translate,
            inputs=[audio_input, source_audio_language, target_audio_language],
            outputs=[transcript_output, detected_language_output, audio_translation_output],
        )

    with gr.Tab("Text Translation"):
        with gr.Row():
            source_text_language = gr.Dropdown(
                choices=language_choices(),
                value="en",
                label="Source language",
            )
            target_text_language = gr.Dropdown(
                choices=language_choices(),
                value="ht",
                label="Target language",
            )

        text_input = gr.Textbox(
            label="Text",
            value="I need help",
            lines=4,
        )
        translate_text_button = gr.Button("Translate", variant="primary")
        text_translation_output = gr.Textbox(label="Translation", lines=4)

        translate_text_button.click(
            fn=translate_text,
            inputs=[text_input, source_text_language, target_text_language],
            outputs=text_translation_output,
        )

    with gr.Tab("About"):
        gr.Markdown(
            """
            ## Demo scope

            This Hugging Face Space is intentionally small enough for free CPU
            hosting. It focuses on English–Haitian Creole speech and text translation
            using Whisper (STT) and NLLB-200 (translation).

            For streaming audio, authentication, usage tracking, and TTS, deploy
            the full FastAPI backend from the main project.
            """
        )


if __name__ == "__main__":
    demo.queue(max_size=16).launch(server_name="0.0.0.0", server_port=7860)
