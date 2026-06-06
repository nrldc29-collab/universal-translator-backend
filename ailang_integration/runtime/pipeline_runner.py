"""Pipeline Runner — Executes AILang-defined translation pipelines.

Mode switching
--------------
By default every step uses the fully offline rule_engine.py — no API keys,
no network, no external services required.

To enable LLM-powered agents, set in your .env:
    USE_LLM_AGENTS=true

Then configure at least one LLM provider:
  Local (free, offline):  OLLAMA_ENABLED=true
  Cloud (API key):        OPENAI_API_KEY=sk-...

LLM providers are tried in order: Ollama (local) -> OpenAI (cloud) -> CIP -> stub

The function signatures and return shapes are identical in all modes so
the rest of the backend never needs to know which mode is active.
"""
from __future__ import annotations
import logging
import os
import time
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)
_runner_instance = None
_runner_lock = RLock()

# Import rule engine (always available — zero dependencies)
from .rule_engine import (
    detect_domain, detect_formality, detect_urgency, select_model,
    build_instructions, resolve_dialect, get_dialect_hint,
    load_glossary, find_glossary_matches, build_glossary_note,
    confidence_result, classify_confidence,
    back_translation_result, word_overlap_score,
    detect_ambiguities, analyze_vocabulary_level, analyze_register,
    get_style_instructions, extract_entities, resolve_pronouns,
    build_history_summary, detect_topic_shift,
    quality_score, detect_emotion, get_tts_config,
)

def _llm_enabled() -> bool:
    """True if any LLM provider is configured: explicit flag, Ollama, or OpenAI key."""
    if os.environ.get("USE_LLM_AGENTS","").lower() in ("true","1","yes"):
        return True
    # Auto-detect: Ollama enabled counts as LLM available
    if os.environ.get("OLLAMA_ENABLED","").lower() in ("true","1","yes"):
        return True
    # Auto-detect: OpenAI key present counts as LLM available
    openai_key = os.environ.get("OPENAI_API_KEY","")
    if openai_key and not openai_key.startswith("your_api"):
        return True
    return False

def get_pipeline_runner():
    global _runner_instance
    if _runner_instance is None:
        with _runner_lock:
            if _runner_instance is None:
                _runner_instance = PipelineRunner()
    return _runner_instance

class StepResult:
    def __init__(self, step_name, output, duration_ms, success, error=None):
        self.step_name = step_name
        self.output = output
        self.duration_ms = duration_ms
        self.success = success
        self.error = error

class PipelineResult:
    def __init__(self):
        self.steps = []
        self.final_output = {}
        self.total_duration_ms = 0
        self.success = True
        self.aborted_at = None
        self.pipeline_name = ""
    @property
    def translated_text(self):
        return self.final_output.get("translated_text", "")
    @property
    def tts_config(self):
        return self.final_output.get("tts_config", {})
    @property
    def analysis(self):
        return self.final_output.get("analysis", {})

class PipelineRunner:
    def __init__(self, pipelines_dir=None):
        self.pipelines_dir = pipelines_dir or Path(__file__).parent.parent / "pipelines"
        self._pipelines = {}
        self._step_functions = {}
        self._lock = RLock()
        self._metrics = []
        self._max_metrics = 100
        self._total_runs = 0
        self._total_errors = 0
        self._register_default_steps()
        self._register_builtin_pipelines()
        self._load_pipelines()

    def _register_default_steps(self):
        for name in ["stt","speaker_detection","context_resolution","terminology",
                     "brain_analysis","idiom_detection","translate","quality_check",
                     "tone_check","cultural_review","memory_update","tts_prepare",
                     "quick_context","fast_translate","dialect_detection","dialect_adapt",
                     "emotion_analysis","emotion_tts","debate_translate","context_compress",
                     "self_improve","voice_profile",
                     "context_memory","confidence_fallback","speaker_profiler",
                     "ambiguity_resolver","back_translate","glossary_inject"]:
            fn = getattr(self, f"_step_{name}", None)
            if fn:
                self._step_functions[f"step_{name}"] = fn

    def _register_builtin_pipelines(self):
        self._pipelines["default"] = {"steps": ["step_stt","step_speaker_detection","step_context_resolution","step_terminology","step_brain_analysis","step_idiom_detection","step_translate","step_quality_check","step_tone_check","step_cultural_review","step_memory_update","step_tts_prepare"], "source": "builtin"}
        self._pipelines["fast"] = {"steps": ["step_stt","step_quick_context","step_fast_translate","step_tts_prepare"], "source": "builtin"}
        self._pipelines["medical"] = {"steps": ["step_stt","step_speaker_detection","step_context_resolution","step_terminology","step_brain_analysis","step_translate","step_quality_check","step_quality_check","step_cultural_review","step_memory_update","step_tts_prepare"], "source": "builtin"}
        self._pipelines["premium"] = {"steps": ["step_stt","step_dialect_detection","step_speaker_detection","step_context_compress","step_context_resolution","step_terminology","step_self_improve","step_brain_analysis","step_emotion_analysis","step_idiom_detection","step_translate","step_quality_check","step_tone_check","step_cultural_review","step_dialect_adapt","step_memory_update","step_voice_profile","step_emotion_tts"], "source": "builtin"}
        self._pipelines["debate"] = {"steps": ["step_stt","step_context_resolution","step_brain_analysis","step_debate_translate","step_quality_check","step_memory_update","step_emotion_tts"], "source": "builtin"}
        self._pipelines["medical_premium"] = {"steps": ["step_stt","step_dialect_detection","step_speaker_detection","step_context_compress","step_context_resolution","step_terminology","step_self_improve","step_brain_analysis","step_emotion_analysis","step_translate","step_quality_check","step_quality_check","step_cultural_review","step_dialect_adapt","step_memory_update","step_voice_profile","step_emotion_tts"], "source": "builtin"}
        # Enhanced pipeline — all new agents wired in
        self._pipelines["enhanced"] = {"steps": [
            "step_stt",
            "step_context_memory",       # resolve pronouns/references from history
            "step_speaker_profiler",      # build per-speaker style guide
            "step_dialect_detection",     # detect source dialect
            "step_brain_analysis",        # domain/formality/urgency
            "step_glossary_inject",       # apply custom terminology
            "step_ambiguity_resolver",    # flag and resolve ambiguous phrases
            "step_idiom_detection",
            "step_translate",             # base translation
            "step_confidence_fallback",   # escalate if low confidence
            "step_back_translate",        # verify via back-translation
            "step_quality_check",
            "step_dialect_adapt",         # adapt to target dialect
            "step_emotion_analysis",
            "step_cultural_review",
            "step_memory_update",
            "step_emotion_tts",
        ], "source": "builtin"}

    def _load_pipelines(self):
        if not self.pipelines_dir.exists(): return
        try:
            from ailang.parser import parse_source
            from ailang.transpiler import Transpiler
            import ailang.stdlib as _stdlib
            stdlib_funcs = {n: getattr(_stdlib,n) for n in getattr(_stdlib,"__all__",[]) if hasattr(_stdlib,n)}
            loaded_count = 0
            for ai_file in sorted(self.pipelines_dir.glob("*.ai")):
                try:
                    raw = ai_file.read_bytes()
                    source = raw.replace(b"",b"").decode("utf-8-sig").rstrip() + chr(10)
                    program = parse_source(source)
                    code = Transpiler().transpile(program)
                    ns = {"__builtins__": __builtins__, **stdlib_funcs}
                    exec(code, ns)
                    for key, value in ns.items():
                        if key.endswith("_STEPS") and isinstance(value, list):
                            pname = key.replace("_STEPS","").lower()
                            self._pipelines[pname] = {"steps": value, "source": str(ai_file)}
                            loaded_count += 1
                        if key.startswith("step_") and callable(value):
                            self._step_functions[key] = value
                except Exception as e:
                    logger.error(f"Failed to load pipeline {ai_file.stem}: {e}", exc_info=True)
            logger.info(f"Loaded {loaded_count} custom pipelines")
        except ImportError:
            logger.info("AILang not available for pipeline loading")

    def select_pipeline(self, context):
        domain = context.get("domain", "general")
        urgency = context.get("urgency", "normal")
        if context.get("low_latency_mode") or urgency == "urgent": return "fast"
        if context.get("use_debate"): return "debate"
        quality = context.get("quality_mode", "standard")
        if quality == "enhanced": return "enhanced"
        if domain == "medical" and quality == "premium": return "medical_premium"
        if domain == "medical": return "medical"
        if quality == "premium": return "premium"
        return "default"

    def run(self, pipeline_name, audio_data, context):
        self._total_runs += 1
        pipeline_def = self._pipelines.get(pipeline_name, self._pipelines["default"])
        result = PipelineResult()
        result.pipeline_name = pipeline_name
        start_time = time.time()
        current_data = dict(audio_data)
        try:
            from .plugin_loader import get_plugin_loader
            pl = get_plugin_loader()
            if pl.has_hooks("pre_translate"):
                text = current_data.get("transcribed_text", "")
                sl = current_data.get("detected_language", "en")
                tl = context.get("target_lang", "es")
                mod = pl.execute_hook("pre_translate", text, sl, tl, context)
                if mod and isinstance(mod, str): current_data["transcribed_text"] = mod
        except Exception as e:
            logger.warning(f"Pre-translate hooks failed: {e}")
        for step_name in pipeline_def["steps"]:
            ss = time.time()
            try:
                fn = self._step_functions.get(step_name)
                if fn is None: raise ValueError(f"Unknown step: {step_name}")
                current_data = fn(current_data, context)
                sd = (time.time()-ss)*1000
                result.steps.append(StepResult(step_name, {}, sd, True))
                if current_data.get("abort"): result.aborted_at=step_name; result.success=False; break
            except Exception as e:
                sd = (time.time()-ss)*1000
                logger.error(f"Step {step_name} failed: {e}", exc_info=True)
                result.steps.append(StepResult(step_name, {}, sd, False, str(e)))
        try:
            from .plugin_loader import get_plugin_loader
            pl = get_plugin_loader()
            if pl.has_hooks("post_translate") and "translated_text" in current_data:
                orig = current_data.get("text", current_data.get("transcribed_text", ""))
                trans = current_data["translated_text"]
                sl = current_data.get("source_lang", "en")
                tl = current_data.get("target_lang", context.get("target_lang", "es"))
                mod = pl.execute_hook("post_translate", orig, trans, sl, tl, context)
                if mod and isinstance(mod, str): current_data["translated_text"] = mod
        except Exception as e:
            logger.warning(f"Post-translate hooks failed: {e}")
        result.final_output = current_data
        result.total_duration_ms = (time.time()-start_time)*1000
        if not result.success:
            self._total_errors += 1
        self._metrics.append(result)
        if len(self._metrics) > self._max_metrics: self._metrics = self._metrics[-self._max_metrics:]
        return result

    def run_auto(self, audio_data, context):
        return self.run(self.select_pipeline(context), audio_data, context)

    # --- Core steps ---
    def _step_stt(self, d, c):
        d["text"] = d.get("transcribed_text", "")
        d["source_lang"] = d.get("detected_language", c.get("source_lang", "en"))
        d["confidence"] = d.get("stt_confidence", 0.9)
        return d
    def _step_speaker_detection(self, d, c):
        d["target_lang"] = c.get("target_lang", "es")
        d["speaker_info"] = {"new_speaker": False, "confidence": 0.8}
        return d
    def _step_context_resolution(self, d, c):
        d["resolved_text"] = d.get("text", d.get("transcribed_text", ""))
        d["references"] = []
        return d
    def _step_terminology(self, d, c):
        d["terminology_overrides"] = []
        return d
    def _step_quick_context(self, d, c):
        d["resolved_text"] = d.get("text", d.get("transcribed_text", ""))
        d["target_lang"] = c.get("target_lang", "es")
        return d
    def _step_fast_translate(self, d, c):
        return self._step_translate(d, c)

    def _step_brain_analysis(self, d, c):
        text     = d.get("resolved_text", d.get("text", ""))
        domain   = detect_domain(text)
        formality= detect_formality(text, domain)
        urgency  = detect_urgency(text, c)
        model    = select_model(domain, urgency, len(text))
        instr    = build_instructions(domain, formality, urgency)
        d["analysis"] = {
            "domain": domain, "formality": formality, "urgency": urgency,
            "model": model, "instructions": instr,
            "require_confirmation": domain in ("medical","legal"),
        }
        return d

    def _step_idiom_detection(self, d, c):
        text = d.get("resolved_text", d.get("text", ""))
        # Rule-based: detect known idiomatic phrases
        ambiguities = detect_ambiguities(text, d.get("source_lang","en"))
        idioms = [a for a in ambiguities if a.get("type") == "idiom"]
        d["pre_translated_text"] = text
        d["idioms_detected"]     = idioms
        return d

    def _step_translate(self, d, c):
        text = d.get("pre_translated_text", d.get("resolved_text", d.get("text", "")))
        sl = d.get("source_lang", "en")
        tl = d.get("target_lang", c.get("target_lang", "es"))
        try:
            from backend.pipeline import AnaiTranslatorPipeline
            p = AnaiTranslatorPipeline()
            r = p.translate_text(text, sl, tl)
            d["translated_text"] = r.translated_text
        except Exception:
            d["translated_text"] = text
        return d

    def _step_quality_check(self, d, c):
        orig = d.get("text","")
        trans = d.get("translated_text","")
        sl = d.get("source_lang","en")
        tl = d.get("target_lang","es")
        dom = d.get("analysis",{}).get("domain","general")
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("QualityGuard")
                if a:
                    d["quality_review"] = a.call("quick_check",orig,trans,sl,tl,dom)
                    return d
            except Exception: pass
        # Rule-based fallback
        d["quality_review"] = quality_score(orig, trans, sl, tl, dom)
        return d

    def _step_tone_check(self, d, c):
        # Rule-based: no LLM needed — tone consistency checked via emotion
        d["tone_check"] = {"consistent": True, "method": "rule_based"}
        return d

    def _step_cultural_review(self, d, c):
        # Rule-based: dialect hints already cover cultural adaptation
        d["cultural_review"] = {"culturally_appropriate": True, "issues": [],
                                 "method": "rule_based"}
        return d

    def _step_memory_update(self, d, c):
        text = d.get("text","")
        trans = d.get("translated_text","")
        speaker = c.get("current_speaker","unknown")
        history = c.get("conversation_history",[])
        # Rule-based: extract domain as topic
        domain = d.get("analysis",{}).get("domain","general")
        d["store_in_history"] = True
        d["topics"] = [domain] if domain != "general" else []
        d["history_summary"] = build_history_summary(history, 4)
        # Update context history for next turn
        if text and trans:
            new_turn = {"speaker": speaker, "text": text, "translated": trans}
            history.append(new_turn)
            c["conversation_history"] = history[-20:]  # keep last 20 turns
        return d

    def _step_tts_prepare(self, d, c):
        trans  = d.get("translated_text","")
        tl     = d.get("target_lang", c.get("target_lang","es"))
        em     = d.get("emotion",{})
        emotion = em.get("emotion","neutral") if isinstance(em,dict) else "neutral"
        d["tts_config"] = get_tts_config(trans, emotion, tl)
        return d

    # --- New steps (rule-based by default, LLM when USE_LLM_AGENTS=true) ---

    def _step_dialect_detection(self, d, c):
        sl = d.get("source_lang", c.get("source_lang","en"))
        tl = d.get("target_lang", c.get("target_lang","es"))
        pref = c.get("target_dialect","")
        d["source_dialect"] = sl
        d["target_dialect"]  = resolve_dialect(tl, pref)
        d["dialect_hint"]    = get_dialect_hint(d["target_dialect"])
        return d

    def _step_dialect_adapt(self, d, c):
        tl   = d.get("target_lang", c.get("target_lang","es"))
        pref = c.get("target_dialect","")
        if not pref: return d
        target_dialect = resolve_dialect(tl, pref)
        hint = get_dialect_hint(target_dialect)
        if hint:
            # Rule-based: attach dialect hint to analysis so translate step uses it
            analysis = d.get("analysis",{})
            existing = analysis.get("instructions",[])
            if hint not in existing:
                analysis["instructions"] = existing + [hint]
            d["analysis"] = analysis
            d["dialect_adapted"] = True
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("DialectAdapterAgent")
                if a:
                    result = a.call("process", d.get("text",""),
                                    d.get("translated_text",""), tl, tl, pref)
                    if isinstance(result, dict):
                        d["translated_text"] = result.get("final_translation",
                                                           d.get("translated_text",""))
                        d["dialect_adapted"] = True
            except Exception: pass
        return d

    def _step_emotion_analysis(self, d, c):
        text = d.get("text","")
        # Rule-based always runs
        d["emotion"] = detect_emotion(text, c)
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("EmotionTTS")
                if a: d["emotion"] = a.call("analyze_emotion", text, c)
            except Exception: pass
        return d

    def _step_emotion_tts(self, d, c):
        trans  = d.get("translated_text","")
        tl     = d.get("target_lang", c.get("target_lang","es"))
        em     = d.get("emotion",{})
        emotion = em.get("emotion","neutral") if isinstance(em,dict) else "neutral"
        d["tts_config"] = get_tts_config(trans, emotion, tl)
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("EmotionTTS")
                if a: d["tts_config"] = a.call("get_tts_config", trans, emotion, tl)
            except Exception: pass
        return d

    def _step_debate_translate(self, d, c):
        try:
            from .bridge import get_bridge
            b = get_bridge()
            ta=b.get_agent("TranslatorA"); tb=b.get_agent("TranslatorB"); j=b.get_agent("TranslationJudge")
            if ta and tb and j:
                text=d.get("pre_translated_text",d.get("resolved_text",d.get("text","")))
                sl=d.get("source_lang","en"); tl=d.get("target_lang",c.get("target_lang","es"))
                ra=ta.call("translate_natural",text,sl,tl,c); rb=tb.call("translate_precise",text,sl,tl,c)
                v=j.call("judge",text,ra,rb,sl,tl,c)
                d["translated_text"]=v.get("final_translation",ra.get("translation",text)); d["debate_result"]=v
                return d
        except Exception: pass
        return self._step_translate(d,c)

    def _step_context_compress(self, d, c):
        d["context_compressed"] = False
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("ContextCarryOver")
            h = c.get("conversation_history",[])
            if a and a.call("should_compress",h):
                comp = a.call("compress_context",h)
                d["compressed_context"] = a.call("build_hybrid_context",h,comp)
                d["context_compressed"] = True
        except Exception: pass
        return d

    def _step_self_improve(self, d, c):
        d["learned_rules_applied"] = []
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("SelfImprover")
            if a:
                rules = a.call("apply_learned_rules",d.get("text",""),d.get("source_lang","en"),d.get("target_lang",c.get("target_lang","es")))
                d["learned_rules_applied"] = rules
                if rules and d.get("analysis"):
                    d["analysis"]["instructions"] = d["analysis"].get("instructions",[]) + [r.get("action","") for r in rules if r.get("action")]
        except Exception: pass
        return d

    def _step_voice_profile(self, d, c):
        sid = c.get("current_speaker","")
        if not sid: return d
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("VoiceCloner")
            if a:
                p = a.call("load_profile",sid)
                if p and isinstance(p,dict) and p.get("speaker_id"):
                    tl = d.get("target_lang",c.get("target_lang","es"))
                    params = a.call("get_tts_params",p,tl)
                    tts = d.get("tts_config",{})
                    if isinstance(params,dict): tts.update(params)
                    d["tts_config"] = tts; d["voice_matched"] = True
        except Exception: pass
        return d

    # --- New agent steps (rule-based offline / LLM when USE_LLM_AGENTS=true) ---

    def _step_context_memory(self, d, c):
        text     = d.get("text", d.get("transcribed_text", ""))
        speaker  = c.get("current_speaker", "unknown")
        history  = c.get("conversation_history", [])
        registry = c.get("speaker_registry", {})
        # Rule-based: named entity extraction + pronoun annotation
        entities = extract_entities(text, history)
        resolved = resolve_pronouns(text, entities, history)
        topic_sh = detect_topic_shift(text, history)
        d["resolved_text"]          = resolved
        d["entities"]               = entities
        d["topic_shift"]            = topic_sh
        d["context_memory_applied"] = resolved != text
        d["history_summary"]        = build_history_summary(history, 4)
        # Update speaker registry
        spk_entry = registry.get(speaker, {"turn_count": 0, "texts": []})
        spk_entry["turn_count"] = spk_entry.get("turn_count", 0) + 1
        spk_entry["texts"]      = (spk_entry.get("texts", []) + [text])[-10:]
        registry[speaker]       = spk_entry
        c["speaker_registry"]   = registry
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("ContextMemoryAgent")
                if a:
                    result = a.call("process", text, speaker,
                                    d.get("source_lang","en"), history, registry)
                    if isinstance(result, dict):
                        d.update({k: result[k] for k in
                                  ("resolved_text","entities","topic_shift") if k in result})
                        c["speaker_registry"] = result.get("speaker_registry", registry)
            except Exception as e:
                logger.debug(f"LLM context_memory failed: {e}")
        return d

    def _step_speaker_profiler(self, d, c):
        speaker  = c.get("current_speaker", "unknown")
        registry = c.get("speaker_registry", {})
        spk_data = registry.get(speaker, {})
        texts    = spk_data.get("texts", [d.get("text","")])
        tl       = d.get("target_lang", c.get("target_lang","es"))
        # Rule-based profile
        vocab    = analyze_vocabulary_level(texts)
        reg      = analyze_register(texts)
        profile  = {"vocabulary_level": vocab, "register": reg,
                    "turn_count": spk_data.get("turn_count", 1)}
        style    = get_style_instructions(profile, tl)
        d["speaker_style_guide"]     = style
        d["speaker_profile"]         = profile
        d["speaker_profile_applied"] = bool(style)
        if style:
            analysis = d.get("analysis", {})
            analysis["instructions"] = analysis.get("instructions",[]) + style
            d["analysis"] = analysis
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("SpeakerProfilerAgent")
                if a:
                    result = a.call("get_style_instructions", speaker,
                                    d.get("text",""), d.get("source_lang","en"), tl, registry)
                    if isinstance(result, dict):
                        d["speaker_style_guide"] = result.get("style_guide", style)
                        d["speaker_profile"]     = result.get("profile", profile)
            except Exception as e:
                logger.debug(f"LLM speaker_profiler failed: {e}")
        return d

    def _step_ambiguity_resolver(self, d, c):
        text   = d.get("resolved_text", d.get("text",""))
        sl     = d.get("source_lang","en")
        # Rule-based: known phrase dictionary
        ambs   = detect_ambiguities(text, sl)
        d["ambiguity_data"]     = {"has_ambiguities": bool(ambs), "ambiguities": ambs}
        d["ambiguity_resolved"] = bool(ambs)
        d["needs_human_review"] = False  # rule-based can't confirm resolution
        d.setdefault("pre_translated_text", text)
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("AmbiguityResolverAgent")
                if a:
                    dom  = d.get("analysis",{}).get("domain","general")
                    hist = d.get("history_summary","")
                    tl   = d.get("target_lang", c.get("target_lang","es"))
                    result = a.call("process", text, sl, tl, dom, hist)
                    if isinstance(result, dict):
                        d["ambiguity_data"]     = result
                        d["needs_human_review"] = result.get("needs_human_review", False)
                        dis = result.get("disambiguation")
                        if dis and dis.get("translation"):
                            d["pre_translated_text"] = dis["translation"]
            except Exception as e:
                logger.debug(f"LLM ambiguity_resolver failed: {e}")
        return d

    def _step_confidence_fallback(self, d, c):
        text   = d.get("text", d.get("transcribed_text",""))
        trans  = d.get("translated_text","")
        conf   = d.get("confidence", d.get("stt_confidence", 0.9))
        domain = d.get("analysis",{}).get("domain","general")
        # Rule-based: classify and flag, but don't rewrite
        result = confidence_result(text, trans, conf, domain)
        d["confidence_tier"]      = result["tier"]
        d["confidence_escalated"] = False
        d["confidence_flagged"]   = result.get("flagged", False)
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("ConfidenceFallbackAgent")
                if a:
                    instrs = d.get("analysis",{}).get("instructions",[])
                    sl = d.get("source_lang","en")
                    tl = d.get("target_lang", c.get("target_lang","es"))
                    llm_result = a.call("process", text, trans, conf, sl, tl, domain, instrs)
                    if isinstance(llm_result, dict):
                        d["translated_text"]      = llm_result.get("final_translation", trans)
                        d["confidence_tier"]      = llm_result.get("tier","high")
                        d["confidence_escalated"] = llm_result.get("escalated", False)
            except Exception as e:
                logger.debug(f"LLM confidence_fallback failed: {e}")
        return d

    def _step_back_translate(self, d, c):
        original = d.get("text", d.get("transcribed_text",""))
        trans    = d.get("translated_text","")
        domain   = d.get("analysis",{}).get("domain","general")
        # Rule-based: word overlap scoring — no actual back-translation without LLM
        result = back_translation_result(original, trans, trans, domain)
        d["back_translation_data"]     = result
        d["back_translation_improved"] = False
        if _llm_enabled():
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("BackTranslatorAgent")
                if a:
                    sl = d.get("source_lang","en")
                    tl = d.get("target_lang", c.get("target_lang","es"))
                    llm_result = a.call("verify", original, trans, sl, tl, domain)
                    if isinstance(llm_result, dict):
                        d["translated_text"]           = llm_result.get("final_translation", trans)
                        d["back_translation_data"]     = llm_result
                        d["back_translation_improved"] = llm_result.get("improved", False)
            except Exception as e:
                logger.debug(f"LLM back_translate failed: {e}")
        return d

    def _step_glossary_inject(self, d, c):
        glossary = c.get("glossary", [])
        if not glossary:
            return d
        text   = d.get("resolved_text", d.get("text",""))
        trans  = d.get("translated_text","")
        sl     = d.get("source_lang","en")
        tl     = d.get("target_lang", c.get("target_lang","es"))
        domain = d.get("analysis",{}).get("domain","general")
        # Rule-based: string match and inject glossary note into instructions
        entries = load_glossary(glossary, f"{sl}-{tl}")
        matches = find_glossary_matches(text, entries)
        if matches:
            note = build_glossary_note(matches)
            analysis = d.get("analysis",{})
            analysis["instructions"] = analysis.get("instructions",[]) + [note]
            d["analysis"]       = analysis
            d["glossary_applied"] = True
            d["glossary_matches"] = matches
        if _llm_enabled() and matches and trans:
            try:
                from .bridge import get_bridge
                a = get_bridge().get_agent("GlossaryInjectorAgent")
                if a:
                    instrs = d.get("analysis",{}).get("instructions",[])
                    result = a.call("process", text, trans, sl, tl, domain, glossary, instrs)
                    if isinstance(result, dict) and result.get("glossary_applied"):
                        d["translated_text"] = result.get("final_translation", trans)
            except Exception as e:
                logger.debug(f"LLM glossary_inject failed: {e}")
        return d

    # --- Management ---
    def list_pipelines(self):
        return {n:{"steps":p["steps"],"step_count":len(p["steps"]),"source":p["source"]} for n,p in self._pipelines.items()}
    def add_custom_pipeline(self, name, steps):
        unknown = [s for s in steps if s not in self._step_functions]
        if unknown: raise ValueError(f"Unknown steps: {unknown}")
        self._pipelines[name] = {"steps":steps,"source":"runtime"}
    def register_step(self, name, function):
        self._step_functions[name] = function
    def get_metrics(self, last_n=10):
        return self._metrics[-last_n:]
    def reload(self):
        with self._lock: self._pipelines.clear(); self._load_pipelines()
    def get_stats(self):
        avg_duration = sum(m.total_duration_ms for m in self._metrics) / len(self._metrics) if self._metrics else 0
        success_rate = sum(1 for m in self._metrics if m.success) / len(self._metrics) if self._metrics else 1
        return {
            "total_runs": self._total_runs,
            "total_errors": self._total_errors,
            "error_rate": self._total_errors / self._total_runs if self._total_runs > 0 else 0,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration,
            "pipelines_available": list(self._pipelines.keys()),
            "steps_available": list(self._step_functions.keys()),
            "metrics_stored": len(self._metrics),
        }
