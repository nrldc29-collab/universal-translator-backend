"""API Routes for AILang Integration.

Adds endpoints to the FastAPI app for:
- GET  /api/ailang/status     — System status (agents, pipelines, plugins)
- POST /api/ailang/reload     — Hot-reload all .ai files
- GET  /api/ailang/pipelines  — List available pipelines
- GET  /api/ailang/plugins    — List loaded plugins
- POST /api/ailang/plugins/{name}/toggle — Enable/disable a plugin
- POST /api/ailang/translate  — Direct translation via AILang pipeline
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def check_ailang_available() -> bool:
    """Check if ailang is installed and importable."""
    try:
        import ailang
        return True
    except ImportError:
        return False


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "es"
    pipeline: str = "auto"
    context: Optional[Dict[str, Any]] = None


class TranslateResponse(BaseModel):
    translated_text: str
    pipeline_used: str
    duration_ms: float
    analysis: Dict[str, Any] = {}
    success: bool = True


def register_ailang_routes(app) -> None:
    """Register AILang API routes on a FastAPI app instance.

    Call this from the main app setup:
        from ailang_integration.runtime.api_routes import register_ailang_routes
        register_ailang_routes(app)
    """
    from fastapi import HTTPException

    @app.get("/api/ailang/status")
    async def ailang_status():
        """Get AILang integration system status."""
        from .backend_hook import get_system_status
        return get_system_status()

    @app.post("/api/ailang/reload")
    async def ailang_reload():
        """Hot-reload all AILang components."""
        from .backend_hook import reload_all
        results = reload_all()
        return {"reloaded": results}

    @app.get("/api/ailang/pipelines")
    async def ailang_pipelines():
        """List available translation pipelines."""
        from .pipeline_runner import get_pipeline_runner
        runner = get_pipeline_runner()
        return runner.list_pipelines()

    @app.get("/api/ailang/plugins")
    async def ailang_plugins():
        """List loaded plugins."""
        from .plugin_loader import get_plugin_loader
        loader = get_plugin_loader()
        return [
            {
                "name": p.name,
                "version": p.version,
                "hooks": p.hooks,
                "enabled": p.enabled,
                "errors": p.load_errors,
            }
            for p in loader.list_plugins()
        ]

    @app.post("/api/ailang/plugins/{name}/toggle")
    async def ailang_toggle_plugin(name: str):
        """Enable or disable a plugin."""
        from .plugin_loader import get_plugin_loader
        loader = get_plugin_loader()
        plugins = {p.name: p for p in loader.list_plugins()}
        if name not in plugins:
            raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

        plugin = plugins[name]
        if plugin.enabled:
            loader.disable_plugin(name)
            return {"name": name, "enabled": False}
        else:
            loader.enable_plugin(name)
            return {"name": name, "enabled": True}

    @app.post("/api/ailang/translate", response_model=TranslateResponse)
    async def ailang_translate(req: TranslateRequest):
        """Translate text using the AILang pipeline directly."""
        from .backend_hook import enhance_translation

        result = enhance_translation(
            text=req.text,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            context=req.context or {},
            pipeline=req.pipeline,
        )

        return TranslateResponse(
            translated_text=result["translated_text"],
            pipeline_used=result.get("pipeline_used", "unknown"),
            duration_ms=result.get("duration_ms", 0),
            analysis=result.get("analysis", {}),
            success=result.get("success", True),
        )

    @app.get("/api/ailang/metrics")
    async def ailang_metrics():
        """Get recent pipeline execution metrics."""
        from .pipeline_runner import get_pipeline_runner
        runner = get_pipeline_runner()
        metrics = runner.get_metrics(20)
        return [
            {
                "pipeline": m.pipeline_name,
                "duration_ms": m.total_duration_ms,
                "success": m.success,
                "steps": len(m.steps),
                "translated_text": m.translated_text[:100] if m.translated_text else "",
            }
            for m in metrics
        ]

    # --- Tier 1/2/3 Feature Endpoints ---

    @app.post("/api/ailang/detect-dialect")
    async def ailang_detect_dialect(text: str = "", language: str = "es"):
        """Detect regional dialect of input text."""
        try:
            from .bridge import get_bridge
            agent = get_bridge().get_agent("DialectAdapter")
            if agent:
                return agent.call("detect_dialect", text, language)
        except Exception as e:
            return {"error": str(e), "dialect": language, "confidence": 0}

    @app.post("/api/ailang/adapt-dialect")
    async def ailang_adapt_dialect(text: str = "", source_dialect: str = "es-ES", target_dialect: str = "es-MX"):
        """Adapt text from one dialect to another."""
        try:
            from .bridge import get_bridge
            agent = get_bridge().get_agent("DialectAdapter")
            if agent:
                return {"adapted_text": agent.call("adapt_to_dialect", text, source_dialect, target_dialect)}
        except Exception as e:
            return {"error": str(e), "adapted_text": text}

    @app.post("/api/ailang/analyze-emotion")
    async def ailang_analyze_emotion(text: str = "", domain: str = "general"):
        """Analyze emotion/sentiment of text for TTS modulation."""
        try:
            from .bridge import get_bridge
            agent = get_bridge().get_agent("EmotionTTS")
            if agent:
                return agent.call("analyze_emotion", text, {"domain": domain})
        except Exception as e:
            return {"error": str(e), "emotion": "neutral", "confidence": 0}

    @app.post("/api/ailang/debate-translate")
    async def ailang_debate_translate(text: str = "", source_lang: str = "en", target_lang: str = "es", domain: str = "general"):
        """Translate using multi-agent debate (two translators + judge)."""
        from .backend_hook import enhance_translation
        result = enhance_translation(
            text=text, source_lang=source_lang, target_lang=target_lang,
            context={"target_lang": target_lang, "domain": domain, "use_debate": True},
            pipeline="debate",
        )
        return result

    @app.post("/api/ailang/compress-context")
    async def ailang_compress_context(history: list = []):
        """Compress a long conversation history into a summary."""
        try:
            from .bridge import get_bridge
            agent = get_bridge().get_agent("ContextCarryOver")
            if agent:
                return agent.call("compress_context", history)
        except Exception as e:
            return {"error": str(e), "summary": "", "turns_compressed": 0}

    @app.post("/api/ailang/log-correction")
    async def ailang_log_correction(original: str = "", bad_translation: str = "", corrected: str = "", source_lang: str = "en", target_lang: str = "es", domain: str = "general"):
        """Log a translation correction for self-improvement."""
        try:
            from .bridge import get_bridge
            agent = get_bridge().get_agent("SelfImprover")
            if agent:
                return agent.call("log_correction", original, bad_translation, corrected, source_lang, target_lang, domain)
        except Exception as e:
            return {"error": str(e), "logged": False}

    @app.post("/api/ailang/visual-translate")
    async def ailang_visual_translate(ocr_text: str = "", source_lang: str = "es", target_lang: str = "en"):
        """Translate OCR text from images with layout preservation."""
        try:
            from .bridge import get_bridge
            bridge = get_bridge()
            agent = bridge.get_agent("VisualTranslator")
            if agent:
                processed = agent.call("process_ocr_text", ocr_text)
                content_type = agent.call("detect_content_type", processed.get("cleaned_text", ocr_text))
                lines = processed.get("lines", [ocr_text])
                translated = agent.call("translate_structured", lines, source_lang, target_lang, content_type.get("type", "sign"))
                overlay = agent.call("format_overlay", translated, content_type.get("type", "sign"))
                return overlay
        except Exception as e:
            return {"error": str(e), "overlay_data": [], "content_type": "unknown"}

    @app.get("/api/ailang/marketplace/search")
    async def ailang_marketplace_search(query: str = ""):
        """Search the plugin marketplace."""
        try:
            from .bridge import get_bridge
            bridge = get_bridge()
            # Try the marketplace agent
            ns = bridge._loaded_modules.get("marketplace", {})
            search_fn = ns.get("search_plugins")
            if search_fn:
                return {"results": search_fn(query)}
        except Exception as e:
            return {"error": str(e), "results": []}

    @app.get("/api/ailang/marketplace/categories")
    async def ailang_marketplace_categories():
        """List plugin marketplace categories."""
        try:
            from .bridge import get_bridge
            ns = get_bridge()._loaded_modules.get("marketplace", {})
            fn = ns.get("list_categories")
            if fn:
                return {"categories": fn()}
        except Exception as e:
            return {"error": str(e), "categories": []}

    @app.get("/api/ailang/agents")
    async def ailang_list_agents():
        """List all loaded AILang agents with their tools."""
        try:
            from .bridge import get_bridge
            bridge = get_bridge()
            agents = []
            for name in bridge.list_agents():
                agent = bridge.get_agent(name)
                agents.append({"name": name, "tools": agent.tools, "instructions": agent.instructions[:200]})
            return {"agents": agents, "total": len(agents)}
        except Exception as e:
            return {"error": str(e), "agents": [], "total": 0}

    @app.post("/api/ailang/hot-reload/start")
    async def ailang_start_hot_reload():
        """Start watching .ai files for changes and auto-reloading."""
        try:
            from .hot_reload import get_hot_reloader
            reloader = get_hot_reloader()
            if not reloader.is_running:
                reloader.start()
                return {"status": "started", "running": True}
            return {"status": "already_running", "running": True}
        except Exception as e:
            return {"error": str(e), "running": False}

    @app.post("/api/ailang/hot-reload/stop")
    async def ailang_stop_hot_reload():
        """Stop watching for file changes."""
        try:
            from .hot_reload import get_hot_reloader
            reloader = get_hot_reloader()
            reloader.stop()
            return {"status": "stopped", "running": False}
        except Exception as e:
            return {"error": str(e)}

    @app.post("/api/ailang/translate/premium")
    async def ailang_translate_premium(req: TranslateRequest):
        """Premium translation with all Tier 1/2/3 features enabled."""
        from .backend_hook import enhance_translation
        ctx = req.context or {}
        ctx["quality_mode"] = "premium"
        ctx["target_lang"] = req.target_lang
        result = enhance_translation(
            text=req.text, source_lang=req.source_lang,
            target_lang=req.target_lang, context=ctx, pipeline="premium",
        )
        return TranslateResponse(
            translated_text=result["translated_text"],
            pipeline_used=result.get("pipeline_used", "premium"),
            duration_ms=result.get("duration_ms", 0),
            analysis=result.get("analysis", {}),
            success=result.get("success", True),
        )

    logger.info("AILang API routes registered at /api/ailang/* (including Tier 1/2/3 features)")
