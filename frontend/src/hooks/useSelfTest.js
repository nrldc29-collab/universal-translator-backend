/**
 * useSelfTest -- run a quick end-to-end check of translation + audio
 * WebSocket and expose the result as a structured object.
 *
 * Returns `{ selfTest, runSelfTest }`.
 *
 * The hook is intentionally pure aside from network calls: callers pass
 * an `onStatus` callback to surface human-readable progress strings in
 * the parent's existing status panel.
 */

import { useCallback, useState } from 'react';

import { authHeaders, htTranslationHasGlossaryTerms, htToEnTranslationLooksValid, responseErrorMessage, withAuthToken } from '../utils';

const INITIAL = {
  status: 'idle',
  translation: '-',
  htTranslation: '-',
  htReverseTranslation: '-',
  htTts: '-',
  liveText: '-',
  sttOnly: '-',
  websocket: '-',
  message: 'Not run yet',
};

async function runTranslateTest(apiUrl, authToken, ensureAuthToken, payload, label) {
  let token = authToken;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    let response = await fetch(`${apiUrl}/translate/text`, {
      method: 'POST',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    });
    if (response.status === 401 && ensureAuthToken) {
      token = await ensureAuthToken({ force: true });
      if (!token) throw new Error('Login required');
      response = await fetch(`${apiUrl}/translate/text`, {
        method: 'POST',
        headers: authHeaders(token, { 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
      });
    }
    if (response.status === 429 && attempt < 3) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000 + attempt * 1500));
      continue;
    }
    if (!response.ok) throw new Error(await responseErrorMessage(response, `${label} failed`));
    const data = await response.json();
    return assertTranslationText(data.translated_text?.trim() || '', label);
  }
  throw new Error(`${label} failed after rate-limit retries`);
}

function assertTranslationText(text, label) {
  if (!text) throw new Error(`${label} returned empty text`);
  if (/^\[[a-z]{2}->[a-z]{2}\]/i.test(text)) {
    throw new Error(`${label} returned placeholder output: ${text}`);
  }
  return text;
}

function testAudioSocket(wsAudioUrl, authToken) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(withAuthToken(wsAudioUrl, authToken));
    const timeout = window.setTimeout(() => {
      socket.close();
      reject(new Error('Audio socket timed out'));
    }, 6000);

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'ping' }));
    };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type !== 'pong') return;
      window.clearTimeout(timeout);
      socket.close();
      resolve('pong');
    };
    socket.onerror = () => {
      window.clearTimeout(timeout);
      reject(new Error('Audio socket failed'));
    };
  });
}

function testHtTts(apiUrl, authToken) {
  return fetch(`${apiUrl}/tts`, {
    method: 'POST',
    headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ text: 'Mwen bezwen èd', language: 'ht' }),
  }).then(async (response) => {
    if (!response.ok) throw new Error(await responseErrorMessage(response, 'HT TTS failed'));
    const data = await response.json();
    if (!data.audio_base64 || String(data.audio_base64).length < 100) {
      throw new Error('HT TTS returned empty audio');
    }
    return 'ok';
  });
}

function testSttOnlySocket(wsAudioUrl, authToken) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(withAuthToken(wsAudioUrl, authToken));
    let started = false;
    const timeout = window.setTimeout(() => {
      socket.close();
      reject(new Error('stt_only socket timed out'));
    }, 15000);

    socket.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      if (data.type === 'error') {
        window.clearTimeout(timeout);
        socket.close();
        reject(new Error(data.message || 'stt_only error'));
        return;
      }
      if (data.type === 'ready' && !started) {
        started = true;
        socket.send(JSON.stringify({
          type: 'start',
          source_language: 'en',
          target_language: 'ht',
          speaker_mode: 'auto',
          speaker: 'auto',
          device_id: 'self-test-stt-only',
          stt_only: true,
          mime_type: 'audio/webm;codecs=opus',
        }));
        return;
      }
      if (data.type === 'listening') {
        const msg = String(data.message || '').toLowerCase();
        if (msg.includes('transcription')) {
          window.clearTimeout(timeout);
          socket.close();
          resolve('ok');
        }
      }
    };
    socket.onerror = () => {
      window.clearTimeout(timeout);
      reject(new Error('stt_only socket failed'));
    };
  });
}

function testLiveTextSocket(wsAudioUrl, authToken) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(withAuthToken(wsAudioUrl, authToken));
    let sawTranslation = false;
    let sawFinalTts = false;
    let started = false;
    const timeout = window.setTimeout(() => {
      socket.close();
      reject(new Error('Live text socket timed out'));
    }, 45000);

    const finish = (value) => {
      window.clearTimeout(timeout);
      socket.close();
      resolve(value);
    };

    socket.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      if (data.type === 'error') {
        window.clearTimeout(timeout);
        socket.close();
        reject(new Error(data.message || 'Live text error'));
        return;
      }
      if (data.type === 'ready' && !started) {
        started = true;
        socket.send(JSON.stringify({
          type: 'start',
          source_language: 'en',
          target_language: 'ht',
          speaker_mode: 'manual',
          speaker: 'A',
          mime_type: 'audio/webm;codecs=opus',
        }));
        socket.send(JSON.stringify({
          type: 'live_text',
          text: 'I need help',
          final: true,
          source_language: 'en',
          target_language: 'ht',
          speaker_mode: 'manual',
          speaker: 'A',
        }));
        return;
      }
      if (data.type === 'live_translation' || data.type === 'partial_translation') {
        if (htTranslationHasGlossaryTerms(data.text)) sawTranslation = true;
      }
      if (data.type === 'tts_end' && !data.partial) sawFinalTts = true;
      if (sawTranslation && sawFinalTts) finish('ok');
    };
    socket.onerror = () => {
      window.clearTimeout(timeout);
      reject(new Error('Live text socket failed'));
    };
  });
}

export default function useSelfTest({ apiUrl, wsAudioUrl, ensureAuthToken, onStatus, connectionStatus } = {}) {
  const [selfTest, setSelfTest] = useState(INITIAL);

  const runSelfTest = useCallback(async () => {
    if (connectionStatus && connectionStatus !== 'online') {
      const message = connectionStatus === 'warming'
        ? 'Models still loading — wait for LIVE'
        : 'Backend offline — start the server first';
      setSelfTest({
        status: 'offline',
        translation: '-',
        htTranslation: '-',
        htReverseTranslation: '-',
        htTts: '-',
        liveText: '-',
        sttOnly: '-',
        websocket: '-',
        message,
      });
      onStatus?.(message);
      return;
    }

    setSelfTest({
      status: 'running',
      translation: 'checking',
      htTranslation: 'checking',
      htReverseTranslation: 'checking',
      htTts: 'checking',
      liveText: 'checking',
      sttOnly: 'checking',
      websocket: 'checking',
      message: 'Running checks...',
    });
    onStatus?.('Running self test...');

    const next = {
      status: 'online',
      translation: '-',
      htTranslation: '-',
      htReverseTranslation: '-',
      htTts: '-',
      liveText: '-',
      sttOnly: '-',
      websocket: '-',
      message: 'Self-test passed',
    };
    const failures = [];
    let authToken = '';

    try {
      authToken = ensureAuthToken ? await ensureAuthToken() : '';
      if (!authToken) throw new Error('Login required');
    } catch (error) {
      failures.push(error.message || 'Login required');
    }

    if (!failures.length) {
      try {
        next.translation = await runTranslateTest(
          apiUrl,
          authToken,
          ensureAuthToken,
          {
            text: 'hello world',
            source_language: 'en',
            target_language: 'es',
            synthesize_audio: false,
          },
          'ES translation test',
        );
      } catch (error) {
        next.translation = 'failed';
        failures.push(error.message || 'Translation test failed');
      }

      try {
        const htText = await runTranslateTest(
          apiUrl,
          authToken,
          ensureAuthToken,
          {
            text: 'I need help',
            source_language: 'en',
            target_language: 'ht',
            synthesize_audio: false,
          },
          'HT translation test',
        );
        if (!htTranslationHasGlossaryTerms(htText)) {
          throw new Error(`HT translation missing expected glossary terms: ${htText}`);
        }
        next.htTranslation = htText;
      } catch (error) {
        next.htTranslation = 'failed';
        failures.push(error.message || 'HT translation test failed');
      }

      try {
        const htReverse = await runTranslateTest(
          apiUrl,
          authToken,
          ensureAuthToken,
          {
            text: 'mwen bezwen èd',
            source_language: 'en',
            target_language: 'ht',
            synthesize_audio: false,
          },
          'HT auto-flip translation test',
        );
        if (!htToEnTranslationLooksValid(htReverse)) {
          throw new Error(`HT auto-flip translation unexpected: ${htReverse}`);
        }
        next.htReverseTranslation = htReverse;
      } catch (error) {
        next.htReverseTranslation = 'failed';
        failures.push(error.message || 'HT→EN translation test failed');
      }

      try {
        next.htTts = await testHtTts(apiUrl, authToken);
      } catch (error) {
        next.htTts = 'failed';
        failures.push(error.message || 'HT TTS test failed');
      }

      try {
        next.websocket = await testAudioSocket(wsAudioUrl, authToken);
      } catch (error) {
        next.websocket = 'failed';
        failures.push(error.message || 'Audio socket test failed');
      }

      try {
        next.sttOnly = await testSttOnlySocket(wsAudioUrl, authToken);
      } catch (error) {
        next.sttOnly = 'failed';
        failures.push(error.message || 'stt_only socket test failed');
      }

      try {
        next.liveText = await testLiveTextSocket(wsAudioUrl, authToken);
      } catch (error) {
        next.liveText = 'failed';
        failures.push(error.message || 'Live text test failed');
      }
    } else {
      next.translation = 'failed';
      next.htTranslation = 'failed';
      next.htReverseTranslation = 'failed';
      next.htTts = 'failed';
      next.liveText = 'failed';
      next.sttOnly = 'failed';
      next.websocket = 'failed';
    }

    if (failures.length) {
      next.status = 'offline';
      next.message = failures.join(' / ');
      onStatus?.('Self-test failed');
    } else {
      next.message = `Self-test passed · ES: ${next.translation} · HT: ${next.htTranslation} · HT→EN: ${next.htReverseTranslation}`;
      onStatus?.('Self-test passed');
    }

    setSelfTest(next);
  }, [apiUrl, wsAudioUrl, ensureAuthToken, onStatus, connectionStatus]);

  return { selfTest, runSelfTest };
}
