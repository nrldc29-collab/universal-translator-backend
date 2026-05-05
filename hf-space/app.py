from functools import lru_cache

import gradio as gr
from faster_whisper import WhisperModel
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


LANGUAGES = {
    "en": "English",
    "es": "Spanish",
}

MODEL_BY_PAIR = {
    ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
    ("es", "en"): "Helsinki-NLP/opus-mt-es-en",
}


@lru_cache(maxsize=1)
def load_whisper() -> WhisperModel:
    return WhisperModel("tiny", device="cpu", compute_type="int8")


@lru_cache(maxsize=2)
def load_translation_model(source_language: str, target_language: str):
    model_name = MODEL_BY_PAIR.get((source_language, target_language))
    if model_name is None:
        raise ValueError("This Space demo supports English <-> Spanish.")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    return tokenizer, model


def transcribe_audio(audio_input, source_language: str = "en") -> tuple[str, str]:
    if audio_input is None:
        return "", ""

    segments, info = load_whisper().transcribe(
        audio_input,
        language=source_language or None,
        beam_size=1,
        vad_filter=True,
    )
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    detected = getattr(info, "language", "") or source_language
    return transcript, detected


def translate_text(text: str, source_language: str = "en", target_language: str = "es") -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if source_language == target_language:
        return text

    tokenizer, model = load_translation_model(source_language, target_language)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = model.generate(**inputs, max_new_tokens=256)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def transcribe_and_translate(audio_input, source_language: str, target_language: str):
    transcript, detected_language = transcribe_audio(audio_input, source_language)
    if not transcript:
        return "", detected_language, ""
    translation = translate_text(transcript, source_language, target_language)
    return transcript, detected_language, translation


def language_choices():
    return [(name, code) for code, name in LANGUAGES.items()]


with gr.Blocks(title="Universal Translator") as demo:
    gr.Markdown("# Universal Translator")
    gr.Markdown("Record or upload speech, transcribe it, and translate between English and Spanish.")

    with gr.Tab("Audio Translation"):
        with gr.Row():
            source_audio_language = gr.Dropdown(
                choices=language_choices(),
                value="en",
                label="Source language",
            )
            target_audio_language = gr.Dropdown(
                choices=language_choices(),
                value="es",
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
                value="es",
                label="Target language",
            )

        text_input = gr.Textbox(
            label="Text",
            value="Hello, how are you?",
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
            hosting. It focuses on English-Spanish speech and text translation.

            For streaming audio, authentication, usage tracking, and TTS, deploy
            the full FastAPI backend from the main project.
            """
        )


if __name__ == "__main__":
    demo.queue(max_size=16).launch(server_name="0.0.0.0", server_port=7860)
