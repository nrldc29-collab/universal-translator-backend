/**
 * useMicPermission -- track the microphone permission state.
 *
 * Possible values: `checking`, `available`, `denied`, `unavailable`.
 *
 * On mount we probe `navigator.mediaDevices.getUserMedia` and (when
 * supported) listen on `navigator.permissions.query({ name:
 * 'microphone' })` for live updates.
 *
 * Returns `{ micPermission, setMicPermission, requestMicPermission }`.
 * `requestMicPermission()` actually pops the browser permission dialog
 * by briefly calling `getUserMedia`, then releases the tracks. It
 * surfaces a human-readable status string via the optional `onStatus`
 * callback.
 */

import { useCallback, useEffect, useState } from 'react';

import { requestAudioStream } from '../utils';

export default function useMicPermission({ onStatus } = {}) {
  const [micPermission, setMicPermission] = useState('checking');

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission('unavailable');
      return undefined;
    }

    setMicPermission('available');
    let permissionRef;
    navigator.permissions
      ?.query?.({ name: 'microphone' })
      .then((permission) => {
        permissionRef = permission;
        setMicPermission(permission.state === 'denied' ? 'denied' : 'available');
        permission.onchange = () => {
          setMicPermission(permission.state === 'denied' ? 'denied' : 'available');
        };
      })
      .catch(() => setMicPermission('available'));

    return () => {
      if (permissionRef) permissionRef.onchange = null;
    };
  }, []);

  const requestMicPermission = useCallback(async () => {
    try {
      const stream = await requestAudioStream();
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission('available');
      onStatus?.('Microphone ready');
    } catch {
      setMicPermission('denied');
      onStatus?.('Microphone permission blocked');
    }
  }, [onStatus]);

  return { micPermission, setMicPermission, requestMicPermission };
}
