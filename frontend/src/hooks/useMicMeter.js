import { useRef, useState } from 'react';

export default function useMicMeter() {
  const micMeterRef = useRef({});
  const silenceDetectRafRef = useRef(0);
  const silenceSeenSpeechRef = useRef(false);
  const silenceStartRef = useRef(0);
  const [micLevel, setMicLevel] = useState(0);

  function startMicMeter(stream) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx || !stream) return;
      const ctx = micMeterRef.current.ctx || new Ctx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.15;
      source.connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      micMeterRef.current = { ctx, analyser, source, data, raf: 0, stopped: false, smoothed: 0 };
      const tick = () => {
        if (micMeterRef.current.stopped) return;
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        let sumSq = 0;
        for (let i = 0; i < data.length; i += 1) {
          const v = (data[i] - 128) / 128;
          const a = Math.abs(v);
          if (a > peak) peak = a;
          sumSq += v * v;
        }
        const rms = Math.sqrt(sumSq / data.length);
        const raw = Math.min(1, rms * 2.4 + peak * 0.6);
        const prev = micMeterRef.current.smoothed || 0;
        const smoothed = raw > prev ? raw : prev * 0.78 + raw * 0.22;
        micMeterRef.current.smoothed = smoothed;
        setMicLevel(smoothed);
        micMeterRef.current.raf = requestAnimationFrame(tick);
      };
      tick();
    } catch (err) {
      console.warn('mic meter failed to start', err);
    }
  }

  function stopMicMeter() {
    const m = micMeterRef.current;
    if (!m) return;
    m.stopped = true;
    if (m.raf) cancelAnimationFrame(m.raf);
    try { m.source && m.source.disconnect(); } catch (e) { console.warn('Mic meter source disconnect error:', e); }
    try { m.analyser && m.analyser.disconnect(); } catch (e) { console.warn('Mic meter analyser disconnect error:', e); }
    try { m.ctx && m.ctx.state !== 'closed' && m.ctx.close(); } catch (e) { console.warn('Mic meter context close error:', e); }
    micMeterRef.current = {};
    setMicLevel(0);
  }

  function stopTracks(stream) {
    stopMicMeter();
    stream?.getTracks().forEach((track) => track.stop());
  }

  function stopSilenceDetector() {
    if (silenceDetectRafRef.current) {
      cancelAnimationFrame(silenceDetectRafRef.current);
      silenceDetectRafRef.current = 0;
    }
    silenceSeenSpeechRef.current = false;
    silenceStartRef.current = 0;
  }

  function startSilenceDetector({ shouldStop, onSilence }) {
    stopSilenceDetector();
    const tick = () => {
      if (shouldStop()) {
        stopSilenceDetector();
        return;
      }
      const level = micMeterRef.current?.smoothed || 0;
      if (!silenceSeenSpeechRef.current && level > 0.12) {
        silenceSeenSpeechRef.current = true;
        silenceStartRef.current = 0;
      } else if (silenceSeenSpeechRef.current && level < 0.045) {
        if (!silenceStartRef.current) {
          silenceStartRef.current = performance.now();
        } else if (performance.now() - silenceStartRef.current > 260) {
          stopSilenceDetector();
          try { onSilence(); } catch (e) {}
          return;
        }
      } else if (level >= 0.045) {
        silenceStartRef.current = 0;
      }
      silenceDetectRafRef.current = requestAnimationFrame(tick);
    };
    silenceDetectRafRef.current = requestAnimationFrame(tick);
  }

  return {
    micLevel,
    micMeterRef,
    startMicMeter,
    stopMicMeter,
    stopTracks,
    startSilenceDetector,
    stopSilenceDetector,
  };
}
