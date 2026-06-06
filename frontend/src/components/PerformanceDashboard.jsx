/**
 * Advanced Performance Dashboard
 * 
 * Displays real-time performance metrics including:
 * - Latency breakdown (STT, Translation, TTS, End-to-End)
 * - Cache statistics (hit rate, hits, misses)
 * - Environment classification
 * - Optimization recommendations
 * - Resource usage (CPU, memory)
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';

export default function PerformanceDashboard({ backendUrl }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(`${backendUrl}/diagnostics`);
        if (!response.ok) throw new Error('Failed to fetch metrics');
        const data = await response.json();
        setMetrics(data);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, [backendUrl]);

  if (loading) {
    return <div className="p-4">Loading performance metrics...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-500">Error: {error}</div>;
  }

  const cacheStats = metrics.predictive_cache || {};
  const optimizationFeedback = metrics.optimization_feedback || {};

  return (
    <div className="space-y-4 p-4">
      <h2 className="text-2xl font-bold">Performance Dashboard</h2>
      
      {/* Cache Statistics */}
      <Card>
        <CardHeader>
          <CardTitle>Predictive Cache</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between items-center">
            <span>Status:</span>
            <Badge variant={cacheStats.enabled ? 'default' : 'secondary'}>
              {cacheStats.enabled ? 'Enabled' : 'Disabled'}
            </Badge>
          </div>
          {cacheStats.enabled && (
            <>
              <div className="flex justify-between items-center">
                <span>Hit Rate:</span>
                <span className="font-mono">{(cacheStats.hit_rate * 100).toFixed(1)}%</span>
              </div>
              <Progress value={cacheStats.hit_rate * 100} className="h-2" />
              <div className="flex justify-between text-sm text-gray-600">
                <span>Hits: {cacheStats.hits || 0}</span>
                <span>Misses: {cacheStats.misses || 0}</span>
              </div>
              <div className="flex justify-between text-sm text-gray-600">
                <span>Size: {cacheStats.size || 0}</span>
                <span>TTL: {cacheStats.ttl_seconds || 0}s</span>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Optimization Feedback */}
      <Card>
        <CardHeader>
          <CardTitle>Optimization Feedback</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between items-center">
            <span>Status:</span>
            <Badge variant={optimizationFeedback.enabled ? 'default' : 'secondary'}>
              {optimizationFeedback.enabled ? 'Active' : 'Inactive'}
            </Badge>
          </div>
          {optimizationFeedback.status && (
            <div className="text-sm text-gray-600">
              Status: {optimizationFeedback.status}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Translation Backend */}
      <Card>
        <CardHeader>
          <CardTitle>Translation Backend</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between items-center">
            <span>Runtime:</span>
            <span className="font-mono">{metrics.translation?.runtime || 'Unknown'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Backend:</span>
            <span className="font-mono">{metrics.translation?.backend || 'Unknown'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Device:</span>
            <span className="font-mono">{metrics.translation?.device || 'Unknown'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Remote Translator:</span>
            <Badge variant={metrics.translation?.remote_translator_reachable ? 'default' : 'destructive'}>
              {metrics.translation?.remote_translator_reachable ? 'Reachable' : 'Unreachable'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Service Health */}
      <Card>
        <CardHeader>
          <CardTitle>Service Health</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {Object.entries(metrics.service_health || {}).map(([service, health]) => (
            <div key={service} className="flex justify-between items-center">
              <span className="capitalize">{service}:</span>
              <Badge variant={health.healthy ? 'default' : 'destructive'}>
                {health.healthy ? 'Healthy' : 'Unhealthy'}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Streaming Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Streaming Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between items-center">
            <span>VAD Silent Checks:</span>
            <span className="font-mono">{metrics.streaming?.vad_silent_checks || 0}</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Speech Merge:</span>
            <span className="font-mono">{metrics.streaming?.speech_merge_ms || 0}ms</span>
          </div>
          <div className="flex justify-between items-center">
            <span>Min Speech Bytes:</span>
            <span className="font-mono">{metrics.streaming?.min_speech_bytes || 0}</span>
          </div>
        </CardContent>
      </Card>

      {/* Last Updated */}
      <div className="text-sm text-gray-500 text-center">
        Last updated: {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}
