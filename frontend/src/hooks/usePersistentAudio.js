import { useState, useRef } from 'react';

export function usePersistentAudio({ debugLog = () => {} } = {}) {
  const [mobileAudioUnlocked, setMobileAudioUnlocked] = useState(false);
  const [audioContextState, setAudioContextState] = useState('unknown');

  const audioContextRef = useRef(null);
  const persistentAudioRef = useRef(null);
  const mobileAudioUnlockedRef = useRef(false);
  const warmupOscRef = useRef(null);
  const warmupGainRef = useRef(null);

  function createPersistentAudio() {
    if (persistentAudioRef.current) return persistentAudioRef.current;
    const audio = document.createElement('audio');
    audio.setAttribute('playsinline', '');
    audio.setAttribute('webkit-playsinline', '');
    audio.setAttribute('preload', 'auto');
    audio.setAttribute('disableRemotePlayback', '');
    audio.setAttribute('x-webkit-airplay', 'deny');
    audio.crossOrigin = 'anonymous';
    audio.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden;';
    document.body.appendChild(audio);
    persistentAudioRef.current = audio;
    return audio;
  }

  async function ensureAudioContext() {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return null;
    if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
      audioContextRef.current = new AudioContextCtor();
    }
    const state = audioContextRef.current.state;
    setAudioContextState(state);
    if (state === 'suspended') {
      try {
        await audioContextRef.current.resume?.();
      } catch (e) {
        console.warn('AudioContext resume failed (no user gesture):', e);
      }
    }
    return audioContextRef.current;
  }

  function stopAudioWarmup() {
    if (warmupOscRef.current) {
      try { warmupOscRef.current.stop(); } catch (e) {}
      warmupOscRef.current = null;
    }
    if (warmupGainRef.current) {
      try { warmupGainRef.current.disconnect(); } catch (e) {}
      warmupGainRef.current = null;
    }
  }

  function destroyPersistentAudio() {
    stopAudioWarmup();
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      try { audioContextRef.current.close(); } catch (e) {}
    }
    if (persistentAudioRef.current) {
      try { document.body.removeChild(persistentAudioRef.current); } catch (e) {}
      persistentAudioRef.current = null;
      mobileAudioUnlockedRef.current = false;
    }
  }

  function synchronousAudioUnlock() {
    if (mobileAudioUnlockedRef.current) return;
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (AudioContextCtor && !audioContextRef.current) {
      audioContextRef.current = new AudioContextCtor();
    }
    const context = audioContextRef.current;
    if (context) {
      if (context.state === 'suspended') {
        context.resume().catch((e) => console.warn('AudioContext resume failed:', e));
      }
      if (!warmupOscRef.current) {
        try {
          const osc = context.createOscillator();
          osc.frequency.value = 40;
          const gain = context.createGain();
          gain.gain.value = 0.0001;
          osc.connect(gain);
          gain.connect(context.destination);
          osc.start();
          warmupOscRef.current = osc;
          warmupGainRef.current = gain;
          debugLog('AudioContext warmup oscillator started');
        } catch (e) {
          console.warn('Failed to start warmup oscillator:', e);
        }
      }
    }
    const audio = createPersistentAudio();
    const sampleRate = 22050;
    const seconds = 0.05;
    const numSamples = Math.floor(sampleRate * seconds);
    const dataSize = numSamples * 2;
    const fileSize = 36 + dataSize;
    const wavBuf = new ArrayBuffer(8 + fileSize);
    const view = new DataView(wavBuf);
    const writeStr = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };
    writeStr(0, 'RIFF');
    view.setUint32(4, fileSize, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, 'data');
    view.setUint32(40, dataSize, true);
    const silentUrl = URL.createObjectURL(new Blob([wavBuf], { type: 'audio/wav' }));
    audio.src = silentUrl;
    audio.muted = true;
    audio.volume = 1;
    let unlockPromise;
    try {
      unlockPromise = audio.play();
    } catch (e) {
      console.warn('Audio unlock play threw:', e);
      try { URL.revokeObjectURL(silentUrl); } catch (e) {}
      return;
    }
    if (unlockPromise && unlockPromise.then) {
      unlockPromise.then(() => {
        debugLog('Audio unlocked successfully (muted priming)');
        mobileAudioUnlockedRef.current = true;
        setMobileAudioUnlocked(true);
      }).catch((e) => {
        console.warn('Audio unlock play failed:', e);
      }).finally(() => {
        try { URL.revokeObjectURL(silentUrl); } catch (e) {}
      });
    } else {
      mobileAudioUnlockedRef.current = true;
      setMobileAudioUnlocked(true);
      try { URL.revokeObjectURL(silentUrl); } catch (e) {}
    }
  }

  async function unlockMobileAudio() {
    synchronousAudioUnlock();
    const context = await ensureAudioContext();
    if (context && context.state === 'suspended') {
      await context.resume().catch((e) => console.warn('AudioContext resume failed:', e));
    }
  }

  async function ensureAudioUnlocked() {
    if (!mobileAudioUnlockedRef.current) {
      await unlockMobileAudio();
    } else {
      const context = await ensureAudioContext();
      if (context && context.state === 'suspended') {
        await context.resume().catch((e) => console.warn('AudioContext resume failed:', e));
      }
    }
  }

  return {
    mobileAudioUnlocked,
    setMobileAudioUnlocked,
    audioContextState,
    setAudioContextState,
    audioContextRef,
    persistentAudioRef,
    mobileAudioUnlockedRef,
    warmupOscRef,
    warmupGainRef,
    createPersistentAudio,
    ensureAudioContext,
    stopAudioWarmup,
    destroyPersistentAudio,
    synchronousAudioUnlock,
    unlockMobileAudio,
    ensureAudioUnlocked,
  };
}
