---
title: Anai Translator
sdk: gradio
app_file: app.py
license: mit
pinned: false
---

# Anai Translator

Speech-to-text and English-Spanish translation demo for Hugging Face Spaces.

This Space is the lightweight demo version of the full Anai Translator
project. It uses:

- faster-whisper with the tiny CPU model for transcription
- Helsinki-NLP OPUS-MT models for English-Spanish translation
- Gradio for the hosted web UI

The full FastAPI backend in the parent project supports the richer local
pipeline, streaming, authentication, and WebSocket workflows.
