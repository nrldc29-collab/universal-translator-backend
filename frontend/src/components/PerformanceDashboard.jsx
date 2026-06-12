/**
 * Performance Dashboard — real-time backend metrics in the app visual style.
 */

import React, { useState, useEffect } from 'react';
import { Activity, Loader2, RefreshCw } from 'lucide-react';

function MetricCard({ title, children }) {
  return (
    <div className="perf-dash-card">
      <h3 className="perf-dash-card-title">{title}</h3>
      <div className="perf-dash-card-body">{children}</div>
    </div>
  );
}

function MetricRow({ label, value, mono = false }) {
  return (
    <div className="perf-dash-row">
      <span className="perf-dash-label">{label}</span>
      <span className={`perf-dash-value${mono ? ' mono' : ''}`}>{value}</span>
    </div>
  );
}

function StatusPill({ ok, okLabel = 'OK', badLabel = 'Issue' }) {
  return (
    <span className={`perf-dash-pill${ok ? ' ok' : ' bad'}`}>
      {ok ? okLabel : badLabel}
    </span>
  );
}

function ProgressBar({ value = 0 }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className="perf-dash-progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="perf-dash-progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export default function PerformanceDashboard({ backendUrl }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchMetrics = async () => {
    if (!backendUrl) {
      setError('No backend URL configured');
      setLoading(false);
      return;
    }
    try {
      const base = backendUrl.replace(/\/$/, '');
      const response = await fetch(`${base}/diagnostics`, { signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error('Failed to fetch metrics');
      const data = await response.json();
      setMetrics(data);
      setError(null);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err?.message || 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000);
    return () => clearInterval(interval);
  }, [backendUrl]);

  if (loading && !metrics) {
    return (
      <div className="perf-dash perf-dash-state" role="status">
        <Loader2 size={18} className="spin-icon" strokeWidth={2.5} />
        <span>Loading performance metrics…</span>
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="perf-dash perf-dash-state perf-dash-error" role="alert">
        <span>{error}</span>
        <button type="button" className="perf-dash-refresh" onClick={fetchMetrics}>
          <RefreshCw size={14} strokeWidth={2.5} />
          Retry
        </button>
      </div>
    );
  }

  const cacheStats = metrics?.predictive_cache || {};
  const optimizationFeedback = metrics?.optimization_feedback || {};
  const hitRate = (cacheStats.hit_rate || 0) * 100;

  return (
    <div className="perf-dash">
      <div className="perf-dash-header">
        <Activity size={16} strokeWidth={2.2} />
        <span>Live performance</span>
        <button type="button" className="perf-dash-refresh" onClick={fetchMetrics} aria-label="Refresh metrics">
          <RefreshCw size={14} strokeWidth={2.5} />
        </button>
      </div>

      <MetricCard title="Predictive cache">
        <MetricRow label="Status" value={<StatusPill ok={cacheStats.enabled} okLabel="Enabled" badLabel="Disabled" />} />
        {cacheStats.enabled && (
          <>
            <MetricRow label="Hit rate" value={`${hitRate.toFixed(1)}%`} mono />
            <ProgressBar value={hitRate} />
            <MetricRow label="Hits / misses" value={`${cacheStats.hits || 0} / ${cacheStats.misses || 0}`} mono />
            <MetricRow label="Size / TTL" value={`${cacheStats.size || 0} · ${cacheStats.ttl_seconds || 0}s`} mono />
          </>
        )}
      </MetricCard>

      <MetricCard title="Optimization">
        <MetricRow
          label="Feedback loop"
          value={<StatusPill ok={optimizationFeedback.enabled} okLabel="Active" badLabel="Inactive" />}
        />
        {optimizationFeedback.status && (
          <MetricRow label="Status" value={optimizationFeedback.status} />
        )}
      </MetricCard>

      <MetricCard title="Bridge backend">
        <MetricRow label="Runtime" value={metrics?.translation?.runtime || '—'} mono />
        <MetricRow label="Backend" value={metrics?.translation?.backend || '—'} mono />
        <MetricRow label="Device" value={metrics?.translation?.device || '—'} mono />
        <MetricRow
          label="Remote bridge"
          value={(
            <StatusPill
              ok={metrics?.translation?.remote_translator_reachable}
              okLabel="Reachable"
              badLabel="Unreachable"
            />
          )}
        />
      </MetricCard>

      {Object.keys(metrics?.service_health || {}).length > 0 && (
        <MetricCard title="Service health">
          {Object.entries(metrics.service_health).map(([service, health]) => (
            <MetricRow
              key={service}
              label={service.replace(/_/g, ' ')}
              value={<StatusPill ok={health.healthy} okLabel="Healthy" badLabel="Unhealthy" />}
            />
          ))}
        </MetricCard>
      )}

      <MetricCard title="Streaming">
        <MetricRow label="VAD silent checks" value={metrics?.streaming?.vad_silent_checks || 0} mono />
        <MetricRow label="Speech merge" value={`${metrics?.streaming?.speech_merge_ms || 0}ms`} mono />
        <MetricRow label="Min speech bytes" value={metrics?.streaming?.min_speech_bytes || 0} mono />
      </MetricCard>

      {lastUpdated && (
        <p className="perf-dash-updated">
          Updated {lastUpdated.toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}
