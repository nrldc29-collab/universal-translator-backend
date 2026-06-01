/**
 * AILangConfigPanel -- UI for configuring AILang agents.
 * Allows enabling/disabling agents and viewing their status.
 */

import React, { useState, useEffect } from 'react';
import { Check, X, RefreshCw, AlertTriangle, CheckCircle } from 'lucide-react';

export default function AILangConfigPanel({ apiUrl, onClose }) {
  const [agents, setAgents] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toggling, setToggling] = useState({});

  const agentNames = [
    'TranslationBrain',
    'ContextMemoryAgent',
    'SpeakerProfilerAgent',
    'DialectAdapterAgent',
    'GlossaryInjectorAgent',
    'AmbiguityResolverAgent',
    'ConfidenceFallbackAgent',
    'BackTranslatorAgent',
    'EmotionTTS',
  ];

  const agentDescriptions = {
    'TranslationBrain': 'Analyzes text for domain, formality, and model selection',
    'ContextMemoryAgent': 'Tracks speaker identity and pronouns across conversation',
    'SpeakerProfilerAgent': 'Learns speaker vocabulary and speaking style',
    'DialectAdapterAgent': 'Adapts translations for regional language variants',
    'GlossaryInjectorAgent': 'Injects custom terminology from glossaries',
    'AmbiguityResolverAgent': 'Detects and resolves ambiguous phrases',
    'ConfidenceFallbackAgent': 'Escalates low-confidence translations',
    'BackTranslatorAgent': 'Verifies translations through back-translation',
    'EmotionTTS': 'Preserves emotional tone in text-to-speech',
  };

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiUrl}/ailang/agents`);
      if (!response.ok) throw new Error('Failed to load agents');
      const data = await response.json();
      setAgents(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleAgent = async (agentName, enabled) => {
    setToggling({ ...toggling, [agentName]: true });
    try {
      const endpoint = enabled ? '/ailang/agent/' + agentName + '/disable' : '/ailang/agent/' + agentName + '/enable';
      const response = await fetch(`${apiUrl}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) throw new Error('Failed to toggle agent');
      await loadAgents();
    } catch (err) {
      setError(err.message);
    } finally {
      setToggling({ ...toggling, [agentName]: false });
    }
  };

  if (loading) {
    return (
      <div className="ailang-config-panel">
        <div className="ailang-config-header">
          <h3>AILang Agent Configuration</h3>
          <button type="button" className="ailang-config-btn close" onClick={onClose}>×</button>
        </div>
        <div className="ailang-config-loading">Loading agents...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ailang-config-panel">
        <div className="ailang-config-header">
          <h3>AILang Agent Configuration</h3>
          <button type="button" className="ailang-config-btn close" onClick={onClose}>×</button>
        </div>
        <div className="ailang-config-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button type="button" className="ailang-config-btn" onClick={loadAgents}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="ailang-config-panel">
      <div className="ailang-config-header">
        <h3>AILang Agent Configuration</h3>
        <div className="ailang-config-header-actions">
          <button type="button" className="ailang-config-btn" onClick={loadAgents} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spinning' : ''} />
            Refresh
          </button>
          <button type="button" className="ailang-config-btn close" onClick={onClose}>×</button>
        </div>
      </div>
      <div className="ailang-config-list">
        {agentNames.map((agentName) => {
          const isEnabled = agents?.[agentName] !== false;
          const isToggling = toggling[agentName];
          return (
            <div key={agentName} className="ailang-config-item">
              <div className="ailang-config-item-info">
                <div className="ailang-config-item-name">{agentName}</div>
                <div className="ailang-config-item-desc">{agentDescriptions[agentName]}</div>
              </div>
              <button
                type="button"
                className={`ailang-config-toggle ${isEnabled ? 'enabled' : 'disabled'}`}
                onClick={() => toggleAgent(agentName, isEnabled)}
                disabled={isToggling}
              >
                {isToggling ? (
                  <RefreshCw size={16} className="spinning" />
                ) : isEnabled ? (
                  <Check size={16} />
                ) : (
                  <X size={16} />
                )}
              </button>
            </div>
          );
        })}
      </div>
      <div className="ailang-config-footer">
        <div className="ailang-config-summary">
          <span className="ailang-config-enabled-count">
            <CheckCircle size={14} />
            {Object.values(agents || {}).filter(Boolean).length} enabled
          </span>
          <span className="ailang-config-disabled-count">
            <X size={14} />
            {Object.values(agents || {}).filter(v => v === false).length} disabled
          </span>
        </div>
      </div>
    </div>
  );
}
