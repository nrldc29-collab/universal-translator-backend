"""AILang Integration — Intelligent translation powered by your custom language.

This package extends the Universal Translator with AILang-powered:
- Translation Brain: Context-aware agent that picks models and strategies
- Pipeline DSL: Declarative, hot-swappable translation pipelines
- Plugin System: User-extensible .ai files for custom behavior
- Quality Control: Multi-agent review for accuracy and cultural fit
- Conversation Memory: Speaker tracking and reference resolution

Quick Start:
    from ailang_integration.runtime.backend_hook import enhance_translation

    result = enhance_translation(
        text="I need to see a doctor",
        source_lang="en",
        target_lang="es",
        context={"domain": "medical", "urgency": "urgent"}
    )
"""

__version__ = "1.0.0"
