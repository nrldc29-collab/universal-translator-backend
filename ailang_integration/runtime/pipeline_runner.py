"""Pipeline Runner — Executes AILang-defined translation pipelines."""
from __future__ import annotations
import logging
import time
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)
_runner_instance = None
_runner_lock = RLock()

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
        self._register_default_steps()
        self._register_builtin_pipelines()
        self._load_pipelines()

    def _register_default_steps(self):
        for name in ["stt","speaker_detection","context_resolution","terminology",
                     "brain_analysis","idiom_detection","translate","quality_check",
                     "tone_check","cultural_review","memory_update","tts_prepare",
                     "quick_context","fast_translate","dialect_detection","dialect_adapt",
                     "emotion_analysis","emotion_tts","debate_translate","context_compress",
                     "self_improve","voice_profile"]:
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

    def _load_pipelines(self):
        if not self.pipelines_dir.exists(): return
        try:
            from ailang.parser import parse_source
            from ailang.transpiler import Transpiler
            import ailang.stdlib as _stdlib
            stdlib_funcs = {n: getattr(_stdlib,n) for n in getattr(_stdlib,"__all__",[]) if hasattr(_stdlib,n)}
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
                        if key.startswith("step_") and callable(value):
                            self._step_functions[key] = value
                except Exception as e:
                    logger.error(f"Failed to load pipeline {ai_file.stem}: {e}")
        except ImportError:
            logger.info("AILang not available for pipeline loading")

    def select_pipeline(self, context):
        domain = context.get("domain", "general")
        urgency = context.get("urgency", "normal")
        if context.get("low_latency_mode") or urgency == "urgent": return "fast"
        if context.get("use_debate"): return "debate"
        quality = context.get("quality_mode", "standard")
        if domain == "medical" and quality == "premium": return "medical_premium"
        if domain == "medical": return "medical"
        if quality == "premium": return "premium"
        return "default"

    def run(self, pipeline_name, audio_data, context):
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
        except Exception: pass
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
                logger.error(f"Step {step_name} failed: {e}")
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
        except Exception: pass
        result.final_output = current_data
        result.total_duration_ms = (time.time()-start_time)*1000
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
        text = d.get("resolved_text", d.get("text", "")).lower()
        med = ["doctor","hospital","medication","allergy","pain","blood","emergency","dose","symptom","diagnosis","surgery","prescription","pharmacy","nurse","fever","infection"]
        leg = ["lawyer","court","contract","rights","judge","arrest","custody"]
        fin = ["money","bank","price","cost","invoice","payment","refund"]
        mh = sum(1 for t in med if t in text)
        lh = sum(1 for t in leg if t in text)
        fh = sum(1 for t in fin if t in text)
        mx = max(mh,lh,fh)
        domain = "general"
        if mx > 0:
            if mh==mx: domain="medical"
            elif lh==mx: domain="legal"
            else: domain="financial"
        model = "claude" if domain in ["medical","legal"] else "fast"
        instr = []
        if domain=="medical": instr=["Use precise medical terminology","Preserve drug names","Preserve dosage numbers"]
        elif domain=="legal": instr=["Maintain legal precision","Keep formal register"]
        elif domain=="financial": instr=["Preserve all numbers exactly"]
        d["analysis"] = {"domain":domain,"formality":"formal" if domain in ["medical","legal"] else "neutral","model":model,"instructions":instr,"require_confirmation":domain in ["medical","legal"]}
        return d

    def _step_idiom_detection(self, d, c):
        d["pre_translated_text"] = d.get("resolved_text", d.get("text", ""))
        d["idioms_detected"] = []
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
        d["quality_review"] = {"pass": True, "score": 7, "issues": []}
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("QualityGuard")
            if a:
                orig = d.get("text",""); trans = d.get("translated_text","")
                sl = d.get("source_lang","en"); tl = d.get("target_lang","es")
                dom = d.get("analysis",{}).get("domain","general")
                d["quality_review"] = a.call("quick_check",orig,trans,sl,tl,dom)
        except Exception: pass
        return d

    def _step_tone_check(self, d, c):
        d["tone_check"] = {"consistent": True}
        return d
    def _step_cultural_review(self, d, c):
        d["cultural_review"] = {"culturally_appropriate": True, "issues": []}
        return d

    def _step_memory_update(self, d, c):
        d["store_in_history"] = True; d["topics"] = []
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("MemoryKeeper")
            if a:
                h = c.get("conversation_history",[])
                spk = c.get("current_speaker","unknown")
                d["context_window"] = a.call("build_context_window",h,spk,8)
                d["topics"] = a.call("extract_topics",d.get("text",""))
        except Exception: pass
        return d

    def _step_tts_prepare(self, d, c):
        d["tts_config"] = {"text":d.get("translated_text",""),"language":d.get("target_lang","es"),"speed":1.0,"emotion":"neutral"}
        return d

    # --- New steps ---
    def _step_dialect_detection(self, d, c):
        d["source_dialect"] = {"dialect":d.get("source_lang","en"),"confidence":0.5,"method":"fallback"}
        d["target_dialect"] = c.get("target_dialect",c.get("target_lang","es"))
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("DialectAdapter")
            if a: d["source_dialect"] = a.call("detect_dialect",d.get("text",""),d.get("source_lang","en"))
        except Exception: pass
        return d

    def _step_dialect_adapt(self, d, c):
        td = c.get("target_dialect"); tl = d.get("target_lang",c.get("target_lang","es"))
        if not td or td == tl: return d
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("DialectAdapter")
            if a: d["translated_text"] = a.call("adapt_to_dialect",d.get("translated_text",""),tl,td); d["dialect_adapted"]=True
        except Exception: pass
        return d

    def _step_emotion_analysis(self, d, c):
        d["emotion"] = {"emotion":"neutral","confidence":0.5,"keyword_hits":0}
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("EmotionTTS")
            if a: d["emotion"] = a.call("analyze_emotion",d.get("text",""),c)
        except Exception: pass
        return d

    def _step_emotion_tts(self, d, c):
        trans = d.get("translated_text",""); tl = d.get("target_lang",c.get("target_lang","es"))
        em = d.get("emotion",{})
        emotion = em.get("emotion","neutral") if isinstance(em,dict) else "neutral"
        d["tts_config"] = {"text":trans,"language":tl,"speed":1.0,"emotion":emotion}
        try:
            from .bridge import get_bridge
            a = get_bridge().get_agent("EmotionTTS")
            if a: d["tts_config"] = a.call("get_tts_config",trans,emotion,tl)
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
                if rules and d.get("analysis"): d["analysis"]["instructions"] = d["analysis"].get("instructions",[]) + [r.get("action","") for r in rules if r.get("action")]
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
