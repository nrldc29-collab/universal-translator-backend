"""AILang Pipeline Manager - orchestrates AILang agents for advanced translation features."""

import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from functools import wraps, lru_cache
from enum import Enum
import hashlib
import json
import threading
import signal

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Custom timeout exception for agent calls."""
    pass


def with_timeout(timeout_seconds: float):
    """Decorator to add timeout to function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout_seconds)
            
            if thread.is_alive():
                # Thread is still running, timeout occurred
                logger.warning(f"Function {func.__name__} timed out after {timeout_seconds}s")
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds}s")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Circuit is open, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for an AILang agent."""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: float = 60.0  # Seconds before attempting recovery
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: CircuitState = CircuitState.CLOSED
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    avg_latency_ms: float = 0.0
    # Performance monitoring
    latency_history: List[float] = field(default_factory=list)
    max_history_size: int = 100
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    def record_success(self, latency_ms: float = 0.0) -> None:
        """Record a successful call."""
        self.failure_count = 0
        self.total_calls += 1
        self.successful_calls += 1
        
        # Update rolling average latency
        if self.avg_latency_ms == 0:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = (self.avg_latency_ms * 0.9) + (latency_ms * 0.1)
        
        # Update latency history for percentile calculations
        self.latency_history.append(latency_ms)
        if len(self.latency_history) > self.max_history_size:
            self.latency_history.pop(0)
        
        # Calculate percentiles
        if self.latency_history:
            sorted_history = sorted(self.latency_history)
            n = len(sorted_history)
            self.p50_latency_ms = sorted_history[int(n * 0.5)]
            self.p95_latency_ms = sorted_history[int(n * 0.95)]
            self.p99_latency_ms = sorted_history[int(n * 0.99)]
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker recovered to CLOSED state")
    
    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.total_calls += 1
        self.failed_calls += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        logger.info("Circuit breaker manually reset to CLOSED state")
    
    def allow_request(self) -> bool:
        """Check if request should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker moved to HALF_OPEN state for recovery test")
                return True
            return False
        
        # HALF_OPEN state - allow one request to test recovery
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics with performance metrics."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.successful_calls / self.total_calls if self.total_calls > 0 else 0.0,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "latency_samples": len(self.latency_history),
            "last_failure_time": self.last_failure_time,
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status with alerts."""
        alerts = []
        status = "healthy"
        
        # Check circuit breaker state
        if self.state == CircuitState.OPEN:
            alerts.append({
                "type": "circuit_open",
                "severity": "critical",
                "message": f"Circuit breaker is OPEN after {self.failure_count} failures"
            })
            status = "critical"
        elif self.state == CircuitState.HALF_OPEN:
            alerts.append({
                "type": "circuit_half_open",
                "severity": "warning",
                "message": "Circuit breaker is in HALF_OPEN state testing recovery"
            })
            status = "degraded"
        
        # Check success rate
        if self.total_calls >= 10:
            success_rate = self.successful_calls / self.total_calls
            if success_rate < 0.5:
                alerts.append({
                    "type": "low_success_rate",
                    "severity": "critical",
                    "message": f"Success rate is {success_rate:.1%} (below 50%)"
                })
                status = "critical"
            elif success_rate < 0.8:
                alerts.append({
                    "type": "low_success_rate",
                    "severity": "warning",
                    "message": f"Success rate is {success_rate:.1%} (below 80%)"
                })
                if status != "critical":
                    status = "degraded"
        
        # Check latency percentiles
        if self.p95_latency_ms > 5000:  # 5 seconds
            alerts.append({
                "type": "high_latency",
                "severity": "warning",
                "message": f"P95 latency is {self.p95_latency_ms:.0f}ms (above 5000ms)"
            })
            if status != "critical":
                status = "degraded"
        
        if self.p99_latency_ms > 10000:  # 10 seconds
            alerts.append({
                "type": "high_latency",
                "severity": "critical",
                "message": f"P99 latency is {self.p99_latency_ms:.0f}ms (above 10000ms)"
            })
            status = "critical"
        
        return {
            "status": status,
            "alerts": alerts,
            "metrics": self.get_stats()
        }


def log_agent_call(agent_name: str):
    """Decorator to log agent calls with timing and error handling."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                logger.debug(f"AILang agent call started: {agent_name}")
                result = func(self, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(f"AILang agent call success: {agent_name} duration={duration_ms:.2f}ms")
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"AILang agent call failed: {agent_name} duration={duration_ms:.2f}ms error={type(e).__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


@dataclass
class AILangContext:
    """Context shared across AILang agents during translation."""
    session_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    speaker_registry: Dict[str, Any] = field(default_factory=dict)
    current_speaker: Optional[str] = None
    domain: str = "general"
    formality: str = "neutral"
    urgency: str = "normal"
    dialect_preference: str = ""
    glossary: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class AILangPipelineManager:
    """Manages AILang agent execution for advanced translation features."""
    
    def __init__(self):
        from backend.config import (
            get_ailang_enabled,
            get_ailang_agent_timeout,
            get_ailang_cache_ttl,
            get_ailang_circuit_failure_threshold,
            get_ailang_circuit_recovery_timeout,
            get_ailang_max_retries,
            get_ailang_enabled_agents,
            get_ailang_disabled_agents,
        )
        
        self._bridge = None
        self._enabled = get_ailang_enabled()
        self._context_cache: Dict[str, AILangContext] = {}
        
        # Circuit breakers for each agent with configurable thresholds
        failure_threshold = get_ailang_circuit_failure_threshold()
        recovery_timeout = get_ailang_circuit_recovery_timeout()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {
            "TranslationBrain": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "ContextMemoryAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "SpeakerProfilerAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "DialectAdapterAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "GlossaryInjectorAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "AmbiguityResolverAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "ConfidenceFallbackAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "BackTranslatorAgent": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
            "EmotionTTS": CircuitBreaker(failure_threshold=failure_threshold, recovery_timeout=recovery_timeout),
        }
        
        # Response cache for expensive operations (configurable TTL)
        self._response_cache: Dict[str, tuple] = {}
        self._cache_ttl = get_ailang_cache_ttl()
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Timeout configuration for agent calls (configurable)
        self._agent_timeout = get_ailang_agent_timeout()
        self._max_retries = get_ailang_max_retries()
        
        # Agent enable/disable configuration from environment
        enabled_agents_str = get_ailang_enabled_agents()
        disabled_agents_str = get_ailang_disabled_agents()
        
        self._enabled_agents: Dict[str, bool] = {
            "TranslationBrain": True,
            "ContextMemoryAgent": True,
            "SpeakerProfilerAgent": True,
            "DialectAdapterAgent": True,
            "GlossaryInjectorAgent": True,
            "AmbiguityResolverAgent": True,
            "ConfidenceFallbackAgent": True,
            "BackTranslatorAgent": True,
            "EmotionTTS": True,
        }
        
        # Apply enabled agents whitelist (if specified)
        if enabled_agents_str:
            enabled_list = [agent.strip() for agent in enabled_agents_str.split(",") if agent.strip()]
            for agent_name in self._enabled_agents:
                self._enabled_agents[agent_name] = agent_name in enabled_list
        
        # Apply disabled agents blacklist (if specified)
        if disabled_agents_str:
            disabled_list = [agent.strip() for agent in disabled_agents_str.split(",") if agent.strip()]
            for agent_name in disabled_list:
                if agent_name in self._enabled_agents:
                    self._enabled_agents[agent_name] = False
        
    def _get_cache_key(self, agent_name: str, *args) -> str:
        """Generate a cache key for agent call."""
        key_parts = [agent_name] + [str(arg) for arg in args]
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response if available and not expired."""
        if cache_key in self._response_cache:
            response, timestamp = self._response_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                self._cache_hits += 1
                logger.debug(f"Cache hit for {cache_key}")
                return response
            else:
                # Expired, remove from cache
                del self._response_cache[cache_key]
        self._cache_misses += 1
        return None
    
    def _cache_response(self, cache_key: str, response: Any) -> None:
        """Cache a response with current timestamp."""
        self._response_cache[cache_key] = (response, time.time())
        # Clean up old cache entries if cache is too large
        if len(self._response_cache) > 1000:
            oldest_keys = sorted(self._response_cache.keys(), key=lambda k: self._response_cache[k][1])[:100]
            for key in oldest_keys:
                del self._response_cache[key]
    
    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._response_cache.clear()
        logger.info("AILang response cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information including size and hit rate."""
        return {
            "size": len(self._response_cache),
            "max_size": 1000,
            "hit_rate": self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0.0,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
        }
    
    def set_agent_enabled(self, agent_name: str, enabled: bool) -> None:
        """Enable or disable a specific agent."""
        if agent_name in self._enabled_agents:
            self._enabled_agents[agent_name] = enabled
            logger.info(f"AILang agent {agent_name} {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning(f"Unknown agent name: {agent_name}")
    
    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled."""
        return self._enabled_agents.get(agent_name, False)
    
    def get_enabled_agents(self) -> Dict[str, bool]:
        """Get all agent enable/disable states."""
        return self._enabled_agents.copy()
    
    def _get_bridge(self):
        """Lazy load AILang bridge."""
        if self._bridge is None:
            try:
                from ailang_integration.runtime.bridge import get_bridge
                self._bridge = get_bridge()
                logger.info("AILang bridge loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load AILang bridge: {e}")
                self._enabled = False
        return self._bridge
    
    def get_or_create_context(self, session_id: str) -> AILangContext:
        """Get or create context for a session."""
        if session_id not in self._context_cache:
            self._context_cache[session_id] = AILangContext(session_id=session_id)
        return self._context_cache[session_id]
    
    def clear_context(self, session_id: str) -> None:
        """Clear context for a session."""
        if session_id in self._context_cache:
            del self._context_cache[session_id]
    
    def _validate_agent_response(self, agent_name: str, response: Any, expected_fields: List[str]) -> bool:
        """Validate that agent response contains expected fields."""
        if not isinstance(response, dict):
            logger.warning(f"AILang agent {agent_name} returned non-dict response: {type(response)}")
            return False
        
        missing_fields = [field for field in expected_fields if field not in response]
        if missing_fields:
            logger.warning(f"AILang agent {agent_name} missing expected fields: {missing_fields}")
            return False
        
        return True
    
    def _call_agent_with_circuit_breaker(self, agent_name: str, func, *args, max_retries: int = None, expected_fields: List[str] = None, timeout: float = None, **kwargs) -> Any:
        """Execute agent call with circuit breaker protection, retry logic, and timeout."""
        circuit_breaker = self._circuit_breakers.get(agent_name)
        if circuit_breaker and not circuit_breaker.allow_request():
            logger.warning(f"Circuit breaker OPEN for {agent_name}, skipping call")
            return None
        
        # Use configured retry count if not specified
        if max_retries is None:
            max_retries = self._max_retries
        
        # Use configured timeout if not specified
        if timeout is None:
            timeout = self._agent_timeout
        
        last_exception = None
        for attempt in range(max_retries + 1):
            start_time = time.time()
            try:
                # Wrap function with timeout
                timeout_func = with_timeout(timeout)(func)
                result = timeout_func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                
                # Validate response if expected fields specified
                if expected_fields and not self._validate_agent_response(agent_name, result, expected_fields):
                    raise ValueError(f"Response validation failed for {agent_name}")
                
                if circuit_breaker:
                    circuit_breaker.record_success(latency_ms)
                if attempt > 0:
                    logger.info(f"AILang agent {agent_name} succeeded on attempt {attempt + 1}")
                return result
            except TimeoutError as e:
                last_exception = e
                logger.warning(f"AILang agent {agent_name} timed out on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    backoff_ms = 100 * (2 ** attempt)
                    time.sleep(backoff_ms / 1000.0)
                else:
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    logger.error(f"AILang agent {agent_name} timed out after {max_retries + 1} attempts")
                    raise
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    # Exponential backoff: 100ms, 200ms, 400ms, etc.
                    backoff_ms = 100 * (2 ** attempt)
                    logger.warning(f"AILang agent {agent_name} failed on attempt {attempt + 1}, retrying in {backoff_ms}ms: {e}")
                    time.sleep(backoff_ms / 1000.0)
                else:
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    logger.error(f"AILang agent {agent_name} failed after {max_retries + 1} attempts: {e}")
                    raise
    
    @log_agent_call("TranslationBrain")
    def analyze_text(self, text: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run TranslationBrain analysis for domain, formality, urgency, model selection."""
        if not self._enabled or not self.is_agent_enabled("TranslationBrain"):
            return {"domain": "general", "formality": "neutral", "urgency": "normal", "model": "fast", "instructions": [], "require_confirmation": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("TranslationBrain")
            if agent:
                result = self._call_agent_with_circuit_breaker("TranslationBrain", agent.call, "analyze", text, source_lang, target_lang, {"urgency": context.urgency, "speaker": context.current_speaker, "turn_count": len(context.conversation_history)}, expected_fields=["domain", "formality", "urgency", "model"])
                if result:
                    # Update context with analysis results
                    context.domain = result.get("domain", "general")
                    context.formality = result.get("formality", "neutral")
                    context.urgency = result.get("urgency", "normal")
                    return result
        except Exception as e:
            logger.error(f"TranslationBrain analysis failed: {e}", exc_info=True)
        
        return {"domain": "general", "formality": "neutral", "urgency": "normal", "model": "fast", "instructions": [], "require_confirmation": False}
    
    @log_agent_call("ContextMemoryAgent")
    def process_context_memory(self, text: str, source_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run ContextMemoryAgent for pronoun resolution and entity tracking."""
        if not self._enabled or not self.is_agent_enabled("ContextMemoryAgent"):
            return {"resolved_text": text, "original_text": text, "resolution_applied": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("ContextMemoryAgent")
            if agent:
                result = self._call_agent_with_circuit_breaker("ContextMemoryAgent", agent.call, "process", text, context.current_speaker or "unknown", source_lang, context.conversation_history, context.speaker_registry, expected_fields=["resolved_text", "original_text"])
                if result:
                    # Update context with new registry
                    context.speaker_registry = result.get("speaker_registry", context.speaker_registry)
                    return result
        except Exception as e:
            logger.error(f"ContextMemoryAgent failed: {e}", exc_info=True)
        
        return {"resolved_text": text, "original_text": text, "resolution_applied": False}
    
    @log_agent_call("SpeakerProfilerAgent")
    def process_speaker_profile(self, text: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run SpeakerProfilerAgent for voice profiling and style adaptation."""
        if not self._enabled or not self.is_agent_enabled("SpeakerProfilerAgent") or not context.current_speaker:
            return {"style_guide": [], "profile": {}}
        
        # Check cache for speaker profile (expensive operation)
        cache_key = self._get_cache_key("SpeakerProfilerAgent", context.current_speaker, source_lang, target_lang)
        cached = self._get_cached_response(cache_key)
        if cached:
            return cached
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("SpeakerProfilerAgent")
            if agent:
                result = self._call_agent_with_circuit_breaker("SpeakerProfilerAgent", agent.call, "get_style_instructions", context.current_speaker, text, source_lang, target_lang, context.speaker_registry, expected_fields=["style_guide", "profile"])
                if result:
                    # Update context with new registry
                    context.speaker_registry = result.get("updated_registry", context.speaker_registry)
                    # Cache the result
                    self._cache_response(cache_key, result)
                    return result
        except Exception as e:
            logger.error(f"SpeakerProfilerAgent failed: {e}", exc_info=True)
        
        return {"style_guide": [], "profile": {}}
    
    @log_agent_call("DialectAdapterAgent")
    def process_dialect_adaptation(self, source_text: str, base_translation: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run DialectAdapterAgent for regional dialect adaptation."""
        if not self._enabled or not self.is_agent_enabled("DialectAdapterAgent") or not context.dialect_preference:
            return {"final_translation": base_translation, "adaptation_applied": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("DialectAdapterAgent")
            if agent:
                result = self._call_agent_with_circuit_breaker("DialectAdapterAgent", agent.call, "process", source_text, base_translation, source_lang, target_lang, context.dialect_preference, expected_fields=["final_translation", "adaptation_applied"])
                if result:
                    return result
        except Exception as e:
            logger.error(f"DialectAdapterAgent failed: {e}", exc_info=True)
        
        return {"final_translation": base_translation, "adaptation_applied": False}
    
    @log_agent_call("GlossaryInjectorAgent")
    def process_glossary_injection(self, text: str, base_translation: str, source_lang: str, target_lang: str, context: AILangContext, instructions: List[str]) -> Dict[str, Any]:
        """Run GlossaryInjectorAgent for custom terminology injection."""
        if not self._enabled or not self.is_agent_enabled("GlossaryInjectorAgent") or not context.glossary:
            return {"final_translation": base_translation, "glossary_applied": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("GlossaryInjectorAgent")
            if agent:
                result = self._call_agent_with_circuit_breaker("GlossaryInjectorAgent", agent.call, "process", text, base_translation, source_lang, target_lang, context.domain, context.glossary, instructions, expected_fields=["final_translation", "glossary_applied"])
                if result:
                    return result
        except Exception as e:
            logger.error(f"GlossaryInjectorAgent failed: {e}", exc_info=True)
        
        return {"final_translation": base_translation, "glossary_applied": False}
    
    @log_agent_call("AmbiguityResolverAgent")
    def process_ambiguity_resolution(self, text: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run AmbiguityResolverAgent for phrase ambiguity detection."""
        if not self._enabled or not self.is_agent_enabled("AmbiguityResolverAgent"):
            return {"has_ambiguities": False, "resolved_text": text, "needs_human_review": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("AmbiguityResolverAgent")
            if agent:
                history_summary = "\n".join([f"{t.get('speaker', 'unknown')}: {t.get('text', '')}" for t in context.conversation_history[-6:]])
                result = self._call_agent_with_circuit_breaker("AmbiguityResolverAgent", agent.call, "process", text, source_lang, target_lang, context.domain, history_summary or "", expected_fields=["has_ambiguities", "resolved_text"])
                if result and isinstance(result, dict) and "has_ambiguities" in result:
                    return result
        except Exception as e:
            logger.error(f"AmbiguityResolverAgent failed: {e}", exc_info=True)
        
        return {"has_ambiguities": False, "resolved_text": text, "needs_human_review": False}
    
    @log_agent_call("ConfidenceFallbackAgent")
    def process_confidence_fallback(self, text: str, base_translation: str, confidence: float, source_lang: str, target_lang: str, context: AILangContext, instructions: List[str]) -> Dict[str, Any]:
        """Run ConfidenceFallbackAgent for low-confidence translation escalation."""
        if not self._enabled or not self.is_agent_enabled("ConfidenceFallbackAgent") or confidence >= 0.65:
            return {"final_translation": base_translation, "escalated": False, "tier": "high"}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("ConfidenceFallbackAgent")
            if agent:
                result = self._call_agent_with_circuit_breaker("ConfidenceFallbackAgent", agent.call, "process", text, base_translation, confidence, source_lang, target_lang, context.domain, instructions, expected_fields=["final_translation", "escalated"])
                if result:
                    return result
        except Exception as e:
            logger.error(f"ConfidenceFallbackAgent failed: {e}", exc_info=True)
        
        return {"final_translation": base_translation, "escalated": False, "tier": "high"}
    
    @log_agent_call("BackTranslatorAgent")
    def process_back_translation(self, original: str, translated: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run BackTranslatorAgent for translation verification."""
        if not self._enabled or not self.is_agent_enabled("BackTranslatorAgent"):
            return {"verified": True, "final_translation": translated, "improved": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("BackTranslatorAgent")
            if agent:
                result = self._call_agent_with_circuit_breaker("BackTranslatorAgent", agent.call, "verify", original, translated, source_lang, target_lang, context.domain, expected_fields=["verified", "final_translation"])
                if result and isinstance(result, dict) and "verified" in result:
                    return result
        except Exception as e:
            logger.error(f"BackTranslatorAgent failed: {e}", exc_info=True)
        
        return {"verified": True, "final_translation": translated, "improved": False}
    
    @log_agent_call("EmotionTTS")
    def process_emotion_tts(self, text: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run EmotionTTS agent for emotional tone preservation in TTS."""
        if not self._enabled or not self.is_agent_enabled("EmotionTTS"):
            return {"emotion": "neutral", "confidence": 0.5, "tts_config": {"speed": 1.0, "pitch_shift": 0, "volume": 1.0, "pause_between_sentences_ms": 200, "voice_style": "default"}}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("EmotionTTS")
            if agent:
                analysis = self._call_agent_with_circuit_breaker("EmotionTTS", agent.call, "analyze_emotion", text, {"domain": context.domain}, expected_fields=["emotion", "confidence"])
                if analysis and isinstance(analysis, dict) and "emotion" in analysis:
                    tts_config = self._call_agent_with_circuit_breaker("EmotionTTS", agent.call, "get_tts_config", text, analysis["emotion"], target_lang, expected_fields=["speed", "pitch_shift", "volume"])
                    if tts_config and isinstance(tts_config, dict) and "speed" in tts_config:
                        return {"emotion": analysis["emotion"], "confidence": analysis.get("confidence", 0.5), "tts_config": tts_config, "analysis": analysis}
        except Exception as e:
            logger.error(f"EmotionTTS failed: {e}", exc_info=True)
        
        return {"emotion": "neutral", "confidence": 0.5, "tts_config": {"speed": 1.0, "pitch_shift": 0, "volume": 1.0, "pause_between_sentences_ms": 200, "voice_style": "default"}}
    
    def add_conversation_turn(self, session_id: str, speaker: str, text: str, translated: str) -> None:
        """Add a conversation turn to the history."""
        context = self.get_or_create_context(session_id)
        context.current_speaker = speaker
        context.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "translated": translated
        })
        # Keep only last 20 turns
        if len(context.conversation_history) > 20:
            context.conversation_history = context.conversation_history[-20:]
    
    def set_glossary(self, session_id: str, glossary: List[Dict[str, Any]]) -> None:
        """Set custom glossary for a session."""
        context = self.get_or_create_context(session_id)
        context.glossary = glossary
    
    def set_dialect_preference(self, session_id: str, dialect: str) -> None:
        """Set dialect preference for a session."""
        context = self.get_or_create_context(session_id)
        context.dialect_preference = dialect
    
    def set_speaker(self, session_id: str, speaker: str) -> None:
        """Set current speaker for a session."""
        context = self.get_or_create_context(session_id)
        context.current_speaker = speaker
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        bridge = self._get_bridge()
        circuit_breaker_stats = {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}
        if bridge:
            return {
                "enabled": self._enabled,
                "active_sessions": len(self._context_cache),
                "bridge_stats": bridge.get_stats(),
                "circuit_breakers": circuit_breaker_stats,
                "cache": self.get_cache_info(),
            }
        return {
            "enabled": self._enabled,
            "active_sessions": len(self._context_cache),
            "bridge_stats": None,
            "circuit_breakers": circuit_breaker_stats,
            "cache": self.get_cache_info(),
        }
    
    def reset_circuit_breaker(self, agent_name: str) -> bool:
        """Manually reset a specific agent's circuit breaker."""
        if agent_name in self._circuit_breakers:
            self._circuit_breakers[agent_name].reset()
            logger.info(f"Reset circuit breaker for agent {agent_name}")
            return True
        return False
    
    def reset_all_circuit_breakers(self) -> int:
        """Reset all circuit breakers. Returns number of agents reset."""
        count = 0
        for agent_name in self._circuit_breakers:
            self._circuit_breakers[agent_name].reset()
            count += 1
        logger.info(f"Reset all {count} circuit breakers")
        return count
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall pipeline health status with alerts."""
        circuit_breaker_health = {name: cb.get_health_status() for name, cb in self._circuit_breakers.items()}
        
        # Aggregate alerts
        all_alerts = []
        overall_status = "healthy"
        
        for agent_name, health in circuit_breaker_health.items():
            all_alerts.extend([{"agent": agent_name, **alert} for alert in health["alerts"]])
            if health["status"] == "critical":
                overall_status = "critical"
            elif health["status"] == "degraded" and overall_status != "critical":
                overall_status = "degraded"
        
        return {
            "overall_status": overall_status,
            "agent_health": circuit_breaker_health,
            "alerts": all_alerts,
            "total_alerts": len(all_alerts),
            "critical_alerts": len([a for a in all_alerts if a["severity"] == "critical"]),
            "warning_alerts": len([a for a in all_alerts if a["severity"] == "warning"]),
        }


# Global pipeline manager instance
_ailang_pipeline: Optional[AILangPipelineManager] = None


def get_ailang_pipeline() -> AILangPipelineManager:
    """Get the global AILang pipeline manager instance."""
    global _ailang_pipeline
    if _ailang_pipeline is None:
        _ailang_pipeline = AILangPipelineManager()
    return _ailang_pipeline
