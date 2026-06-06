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

import { authHeaders, responseErrorMessage, withAuthToken } from '../utils';

const INITIAL = {
  status: 'idle',
  translation: '-',
  htTranslation: '-',
  websocket: '-',
  message: 'Not run yet',
};

async function runTranslateTest(apiUrl, authToken, ensureAuthToken, payload, label) {
  let token = authToken;
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
  if (!response.ok) throw new Error(await responseErrorMessage(response, `${label} failed`));
  const data = await response.json();
  return assertTranslationText(data.translated_text?.trim() || '', label);
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
      websocket: 'checking',
      message: 'Running checks...',
    });
    onStatus?.('Running self test...');

    const next = {
      status: 'online',
      translation: '-',
      htTranslation: '-',
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
        const lower = htText.toLowerCase();
        if (!('èd' in lower || 'ed' in lower || 'bezwen' in lower)) {
          throw new Error(`HT translation missing expected glossary terms: ${htText}`);
        }
        next.htTranslation = htText;
      } catch (error) {
        next.htTranslation = 'failed';
        failures.push(error.message || 'HT translation test failed');
      }

      try {
        next.websocket = await testAudioSocket(wsAudioUrl, authToken);
      } catch (error) {
        next.websocket = 'failed';
        failures.push(error.message || 'Audio socket test failed');
      }
    } else {
      next.translation = 'failed';
      next.htTranslation = 'failed';
      next.websocket = 'failed';
    }

    if (failures.length) {
      next.status = 'offline';
      next.message = failures.join(' / ');
      onStatus?.('Self-test failed');
    } else {
      next.message = `Self-test passed · ES: ${next.translation} · HT: ${next.htTranslation}`;
      onStatus?.('Self-test passed');
    }

    setSelfTest(next);
  }, [apiUrl, wsAudioUrl, ensureAuthToken, onStatus, connectionStatus]);

  return { selfTest, runSelfTest };
}
