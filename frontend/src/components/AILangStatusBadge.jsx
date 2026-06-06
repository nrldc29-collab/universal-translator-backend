/**
 * AILangStatusBadge -- Shows AILang/Ollama intelligence layer status.
 * Green:  LLM active (Ollama or OpenAI)
 * Yellow: Degraded (unreachable, falling back to offline rules)
 * Gray:   Offline (no LLM configured, rule-based only)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Brain, CloudOff, Zap, AlertTriangle, Wifi } from 'lucide-react';

export default function AILangStatusBadge({ apiUrl }) {
  const [status, setStatus] = useState(null);

  const fetchStatus = useCallback(async () => {
    if (!apiUrl) return;
    try {
      const res = await fetch(`${apiUrl}/health/ollama`, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) return;
      const data = await res.json();
      // Map /health/ollama response to badge status
      const warmup = data.warmup || {};
      setStatus({
        ...warmup,
        reachable: data.reachable,
        model_loaded: data.model_loaded,
        models: data.models,
        ollama_model: data.model,
        ollama_url: data.url,
        enabled: data.enabled,
      });
    } catch {
      // Silently fail — badge degrades gracefully
    }
  }, [apiUrl]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (!status) {
    return (
      <div className="ailang-status-badge loading" role="status" aria-label="AILang status: checking">
        <Brain size={12} className="ailang-status-icon" />
        <span className="ailang-status-text">AILang</span>
      </div>
    );
  }

  const { status: statusCode, ollama_model, warmup_ms, message, reachable, model_loaded, enabled } = status;

  // Determine display based on status + live reachability
  let icon, label, tooltip, colorClass;

  // Ollama not enabled at all
  if (!enabled && statusCode !== 'cloud_mode') {
    icon = <CloudOff size={12} />;
    label = 'AILang: Offline';
    tooltip = message || 'No LLM configured — rule-based agents only';
    colorClass = 'offline';
  }
  // Active warm-up or live reachable
  else if (statusCode === 'active' || (reachable && model_loaded)) {
    icon = <Zap size={12} />;
    label = ollama_model ? `AILang: ${ollama_model}` : 'AILang: Active';
    tooltip = message || 'Ollama model loaded and ready';
    colorClass = 'active';
  }
  // Cloud LLM mode (OpenAI)
  else if (statusCode === 'cloud_mode') {
    icon = <Wifi size={12} />;
    label = 'AILang: Cloud';
    tooltip = message || 'OpenAI cloud LLM active';
    colorClass = 'active';
  }
  // Degraded — enabled but not reachable or model not loaded
  else {
    icon = <AlertTriangle size={12} />;
    label = 'AILang: Degraded';
    tooltip = message || (reachable ? 'Model not found in Ollama' : 'Ollama unreachable — using offline fallbacks');
    colorClass = 'degraded';
  }

  return (
    <div
      className={`ailang-status-badge ${colorClass}`}
      role="status"
      aria-label={`AILang status: ${label}`}
      title={tooltip}
    >
      <span className="ailang-status-icon">{icon}</span>
      <span className="ailang-status-text">{label}</span>
      {statusCode === 'active' && warmup_ms != null && (
        <span className="ailang-status-detail">{warmup_ms < 1000 ? `${warmup_ms}ms` : `${(warmup_ms / 1000).toFixed(1)}s`}</span>
      )}
    </div>
  );
}
