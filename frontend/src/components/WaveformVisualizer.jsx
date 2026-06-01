/**
 * WaveformVisualizer -- Animated sound waveform visualization
 * Shows real-time audio activity with smooth, performant canvas-based rendering
 */

import React, { useEffect, useRef, useCallback } from 'react';

export default function WaveformVisualizer({
  micLevel = 0,
  isListening = false,
  isSpeaking = false,
  color = '#22d3ee',
  barCount = 32,
  className = '',
}) {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const barsRef = useRef(new Array(barCount).fill(0));
  const targetBarsRef = useRef(new Array(barCount).fill(0));
  const timeRef = useRef(0);

  const animate = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    // Set canvas size with DPR for sharp rendering
    if (canvas.width !== rect.width * dpr || canvas.height !== rect.height * dpr) {
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    }

    const width = rect.width;
    const height = rect.height;
    const centerY = height / 2;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Generate target values based on state
    timeRef.current += 0.05;
    const baseActivity = isListening ? micLevel : isSpeaking ? 0.6 : 0.1;
    
    for (let i = 0; i < barCount; i++) {
      const normalizedIndex = i / (barCount - 1);
      const distanceFromCenter = Math.abs(normalizedIndex - 0.5) * 2;
      const centerBoost = 1 - distanceFromCenter * 0.4;
      
      // Add sine wave animation
      const wave = Math.sin(timeRef.current + i * 0.3) * 0.3;
      const noise = Math.random() * 0.15;
      
      let target;
      if (isListening) {
        // Active listening: responsive to mic level
        target = (baseActivity * centerBoost + wave * 0.5 + noise) * 0.9;
      } else if (isSpeaking) {
        // Speaking: rhythmic pattern
        target = (0.5 + wave * 0.4 + Math.sin(timeRef.current * 2 + i * 0.5) * 0.2) * centerBoost;
      } else {
        // Idle: gentle ambient movement
        target = (0.05 + wave * 0.1) * 0.3;
      }
      
      targetBarsRef.current[i] = Math.max(0.02, Math.min(1, target));
    }

    // Smooth interpolation
    for (let i = 0; i < barCount; i++) {
      const diff = targetBarsRef.current[i] - barsRef.current[i];
      barsRef.current[i] += diff * 0.15; // Smooth easing
    }

    // Draw bars
    const barWidth = (width / barCount) * 0.7;
    const barGap = (width / barCount) * 0.3;

    for (let i = 0; i < barCount; i++) {
      const x = i * (barWidth + barGap) + barGap / 2;
      const barHeight = barsRef.current[i] * height * 0.85;
      const y = centerY - barHeight / 2;

      // Create gradient
      const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
      if (isListening) {
        gradient.addColorStop(0, '#22d3ee');
        gradient.addColorStop(0.5, '#0ea5e9');
        gradient.addColorStop(1, '#6366f1');
      } else if (isSpeaking) {
        gradient.addColorStop(0, '#34d399');
        gradient.addColorStop(0.5, '#10b981');
        gradient.addColorStop(1, '#059669');
      } else {
        gradient.addColorStop(0, 'rgba(148, 163, 184, 0.4)');
        gradient.addColorStop(1, 'rgba(148, 163, 184, 0.1)');
      }

      // Draw bar with rounded corners
      ctx.fillStyle = gradient;
      ctx.beginPath();
      const radius = barWidth / 3;
      ctx.roundRect(x, y, barWidth, barHeight, radius);
      ctx.fill();

      // Add glow effect for active states
      if ((isListening || isSpeaking) && barsRef.current[i] > 0.3) {
        ctx.shadowColor = isListening ? '#22d3ee' : '#34d399';
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }

    animationRef.current = requestAnimationFrame(animate);
  }, [isListening, isSpeaking, micLevel, barCount]);

  useEffect(() => {
    animate();
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [animate]);

  return (
    <canvas
      ref={canvasRef}
      className={`waveform-visualizer ${isListening || isSpeaking ? 'active' : ''} ${className}`}
      aria-hidden="true"
    />
  );
}
