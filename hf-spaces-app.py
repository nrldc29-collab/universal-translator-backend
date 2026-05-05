import gradio as gr
import torch
from faster_whisper import WhisperModel
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import numpy as np
import asyncio

# Load models (will be cached after first run)
print("Loading Whisper model...")
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

print("Loading translation model (English-Spanish)...")
translator_name = "Helsinki-NLP/opus-mt-en-es"
translator_tokenizer = AutoTokenizer.from_pretrained(translator_name)
translator = AutoModelForSeq2SeqLM.from_pretrained(translator_name)

print("Models loaded!")

def transcribe_audio(audio_input):
    """Transcribe audio to text using Whisper"""
    if audio_input is None:
        return "", ""
    
    try:
        # audio_input is (sample_rate, audio_array) from Gradio
        sample_rate, audio_data = audio_input
        
        # Convert to float32 and normalize
        audio = audio_data.astype(np.float32) / 32768.0
        
        # Transcribe
        segments, info = whisper_model.transcribe(
            audio,
            language="en",
            beam_size=1
        )
        
        transcript = " ".join(segment.text for segment in segments)
        return transcript, info.language
    except Exception as e:
        return f"Error: {str(e)}", ""

def translate_text(text, source_lang="en", target_lang="es"):
    """Translate text using MarianMT"""
    if not text or text.startswith("Error"):
        return text
    
    try:
        if source_lang == "en" and target_lang == "es":
            model_name = "Helsinki-NLP/opus-mt-en-es"
            tok = translator_tokenizer
            model = translator
        elif source_lang == "es" and target_lang == "en":
            # For Spanish->English, we'd need another model
            return text  # Return original for now
        else:
            return text
        
        # Translate
        inputs = tok.encode(text, return_tensors="pt")
        outputs = model.generate(inputs, max_length=512)
        translation = tok.decode(outputs[0], skip_special_tokens=True)
        return translation
    except Exception as e:
        return f"Error: {str(e)}"

# Gradio interface
with gr.Blocks(title="Universal Translator") as demo:
    gr.Markdown("# 🌍 Universal Translator")
    gr.Markdown("Record audio, transcribe to text, and translate in real-time")
    
    with gr.Tab("Audio Translation"):
        with gr.Row():
            audio_input = gr.Audio(
                label="🎤 Record or Upload Audio",
                type="numpy",
                sources=["microphone", "upload"]
            )
            language_output = gr.Textbox(label="Detected Language", interactive=False)
        
        transcript = gr.Textbox(label="📝 Transcript (English)", interactive=False)
        translate_btn = gr.Button("🔄 Translate to Spanish")
        translation = gr.Textbox(label="📖 Translation (Spanish)", interactive=False)
        
        # Connect transcribe to audio input change
        audio_input.change(
            fn=transcribe_audio,
            inputs=audio_input,
            outputs=[transcript, language_output]
        )
        
        # Connect translate button
        translate_btn.click(
            fn=translate_text,
            inputs=[transcript, gr.State("en"), gr.State("es")],
            outputs=translation
        )
    
    with gr.Tab("Text Translation"):
        with gr.Row():
            with gr.Column():
                text_input = gr.Textbox(
                    label="📝 Enter Text (English)",
                    placeholder="Hello, how are you?",
                    lines=3
                )
            with gr.Column():
                text_output = gr.Textbox(
                    label="📖 Spanish Translation",
                    interactive=False,
                    lines=3
                )
        
        translate_text_btn = gr.Button("🔄 Translate")
        translate_text_btn.click(
            fn=translate_text,
            inputs=[text_input, gr.State("en"), gr.State("es")],
            outputs=text_output
        )
    
    with gr.Tab("About"):
        gr.Markdown("""
        ## How it works
        
        1. **Audio Input**: Record or upload audio
        2. **Transcription**: Whisper converts speech to text
        3. **Translation**: MarianMT translates English to Spanish
        
        ## Models
        
        - **Whisper (tiny)**: Speech-to-text (fast, CPU-friendly)
        - **Helsinki-NLP/opus-mt-en-es**: English-to-Spanish translation
        
        ## Status
        
        ✅ Running on Hugging Face Spaces
        
        All processing happens on-device. No data is sent to external servers.
        """)

if __name__ == "__main__":
    demo.launch(share=False)
