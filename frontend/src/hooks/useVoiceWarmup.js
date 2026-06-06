import { useRef } from 'react';
import { authHeaders } from '../utils';

export function useVoiceWarmup({
  apiUrl,
  authToken,
  targetLanguage,
  warmupPhrases,
  cooldownMs,
  prefetchTimeoutMs,
}) {
  const voiceWarmupRef = useRef({ inFlight: false, lastAtByLanguage: {} });

  function resolveAudioUrl(audioUrl) {
    const rawUrl = String(audioUrl || '').trim();
    if (!rawUrl) return '';
    try {
      const baseUrl = apiUrl || window.location.origin;
      return new URL(rawUrl, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`).toString();
    } catch (error) {
      console.warn('Unable to resolve audio URL:', error);
      return rawUrl;
    }
  }

  async function prefetchAudioUrl(audioUrl, reason = 'warmup') {
    const directAudioUrl = resolveAudioUrl(audioUrl);
    if (!directAudioUrl) return false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), prefetchTimeoutMs);
    try {
      const response = await fetch(directAudioUrl, { cache: 'force-cache', signal: controller.signal });
      window.clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      window.clearTimeout(timeoutId);
      if (error?.name !== 'AbortError') console.warn('voice audio prefetch failed:', reason, error);
      return false;
    }
  }

  async function warmVoiceCache(reason = 'idle') {
    const current = voiceWarmupRef.current;
    const now = Date.now();
    const language = targetLanguage || 'ht';
    const phrases = warmupPhrases[language] || warmupPhrases.ht || warmupPhrases.es;
    // Handle object format with categories (casual, formal, greeting) or array format
    let textToWarm;
    if (typeof phrases === 'object' && !Array.isArray(phrases)) {
      // New categorized format - pick a random category and phrase
      const categories = Object.keys(phrases);
      const randomCategory = categories[Math.floor(Math.random() * categories.length)];
      const categoryPhrases = phrases[randomCategory];
      textToWarm = Array.isArray(categoryPhrases) 
        ? categoryPhrases[Math.floor(Math.random() * categoryPhrases.length)]
        : categoryPhrases;
    } else if (Array.isArray(phrases)) {
      // Old array format
      textToWarm = phrases[Math.floor(Math.random() * phrases.length)];
    } else {
      // String format (fallback)
      textToWarm = phrases;
    }
    const lastAt = current.lastAtByLanguage?.[language] || 0;
    if (current.inFlight || now - lastAt < cooldownMs) return false;
    current.inFlight = true;
    current.lastAtByLanguage = { ...(current.lastAtByLanguage || {}), [language]: now };
    try {
      const response = await fetch(`${apiUrl}/tts`, {
        method: 'POST',
        headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
        cache: 'no-store',
        body: JSON.stringify({ text: textToWarm, language, response_format: 'url', warmup_reason: reason }),
      });
      if (!response.ok) return false;
      const data = await response.json().catch(() => null);
      if (data?.audio_url) await prefetchAudioUrl(data.audio_url, reason);
      return true;
    } catch (error) {
      console.warn('voice warmup failed:', error);
      return false;
    } finally {
      current.inFlight = false;
    }
  }

  return { voiceWarmupRef, resolveAudioUrl, prefetchAudioUrl, warmVoiceCache };
}
