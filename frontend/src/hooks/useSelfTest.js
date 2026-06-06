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
  websocket: '-',
  message: 'Not run yet',
};

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
        websocket: '-',
        message,
      });
      onStatus?.(message);
      return;
    }

    setSelfTest({
      status: 'running',
      translation: 'checking',
      websocket: 'checking',
      message: 'Running checks...',
    });
    onStatus?.('Running self test...');

    const next = {
      status: 'online',
      translation: '-',
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
        const response = await fetch(`${apiUrl}/translate/text`, {
          method: 'POST',
          headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            text: 'hello world',
            source_language: 'en',
            target_language: 'es',
            synthesize_audio: false,
          }),
        });
        if (response.status === 401 && ensureAuthToken) {
          authToken = await ensureAuthToken({ force: true });
          if (!authToken) throw new Error('Login required');
          const retry = await fetch(`${apiUrl}/translate/text`, {
            method: 'POST',
            headers: authHeaders(authToken, { 'Content-Type': 'application/json' }),
            body: JSON.stringify({
              text: 'hello world',
              source_language: 'en',
              target_language: 'es',
              synthesize_audio: false,
            }),
          });
          if (!retry.ok) throw new Error(await responseErrorMessage(retry, 'Translation test failed'));
          const retryData = await retry.json();
          if (!retryData.translated_text?.trim()) throw new Error('Translation returned empty text');
          if (/^\[[a-z]{2}->[a-z]{2}\]/i.test(retryData.translated_text)) {
            throw new Error(`Translation returned placeholder output: ${retryData.translated_text}`);
          }
          next.translation = retryData.translated_text;
        } else {
          if (!response.ok) {
            throw new Error(await responseErrorMessage(response, 'Translation test failed'));
          }
          const data = await response.json();
          if (!data.translated_text?.trim()) throw new Error('Translation returned empty text');
          if (/^\[[a-z]{2}->[a-z]{2}\]/i.test(data.translated_text)) {
            throw new Error(`Translation returned placeholder output: ${data.translated_text}`);
          }
          next.translation = data.translated_text;
        }
      } catch (error) {
        next.translation = 'failed';
        failures.push(error.message || 'Translation test failed');
      }

      try {
        next.websocket = await testAudioSocket(wsAudioUrl, authToken);
      } catch (error) {
        next.websocket = 'failed';
        failures.push(error.message || 'Audio socket test failed');
      }
    } else {
      next.translation = 'failed';
      next.websocket = 'failed';
    }

    if (failures.length) {
      next.status = 'offline';
      next.message = failures.join(' / ');
      onStatus?.('Self-test failed');
    } else {
      onStatus?.('Self-test passed');
    }

    setSelfTest(next);
  }, [apiUrl, wsAudioUrl, ensureAuthToken, onStatus, connectionStatus]);

  return { selfTest, runSelfTest };
}
