/**
 * useInterpreterState -- single source of truth for the seven boolean
 * flags that describe where the live-translation pipeline currently is:
 *
 *   recording          -- mic is capturing audio (record-and-upload path)
 *   streaming          -- mic is streaming audio over the /ws/audio socket
 *   processing         -- backend is busy (STT, translation, or TTS)
 *   playing            -- translated audio is currently audible
 *   interpreterMode    -- continuous duplex interpreter mode is active
 *   instantListening   -- instant-on speech-recognition path is active
 *   liveAssistActive   -- the NAIA live-assist socket is open
 *
 * These flags are coupled -- for example, when `streaming` becomes true,
 * `recording` is also true, and `processing` flips between transcript
 * chunks. A reducer keeps the transitions explicit and discourages
 * accidentally setting two flags out of sync.
 *
 * To minimise call-site churn the hook also returns individually-named
 * shim setters (`setRecording`, `setStreaming`, ...) that compose into
 * the same reducer. New transitions should prefer `dispatch` with a
 * named action; legacy code can keep using the shims.
 *
 * Exported actions:
 *   SET_FLAG     -- { type, flag, value }
 *   SET_FLAGS    -- { type, flags: { ... } }
 *   RESET        -- reset every flag back to its initial false value
 */

import { useCallback, useMemo, useReducer } from 'react';

const INITIAL = {
  recording: false,
  streaming: false,
  processing: false,
  playing: false,
  interpreterMode: false,
  instantListening: false,
  liveAssistActive: false,
};

export const ACTIONS = {
  SET_FLAG: 'set_flag',
  SET_FLAGS: 'set_flags',
  RESET: 'reset',
};

function reducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_FLAG: {
      const next = typeof action.value === 'function' ? action.value(state[action.flag]) : action.value;
      if (state[action.flag] === next) return state;
      return { ...state, [action.flag]: next };
    }
    case ACTIONS.SET_FLAGS: {
      const next = { ...state, ...action.flags };
      // Bail out if nothing actually changed.
      for (const key of Object.keys(action.flags)) {
        if (state[key] !== next[key]) return next;
      }
      return state;
    }
    case ACTIONS.RESET:
      return INITIAL;
    default:
      return state;
  }
}

function makeSetter(dispatch, flag) {
  return (value) => dispatch({ type: ACTIONS.SET_FLAG, flag, value });
}

export default function useInterpreterState() {
  const [state, dispatch] = useReducer(reducer, INITIAL);

  // Shim setters keep the existing call sites in main.jsx working
  // verbatim. Each setter is stable across renders.
  const setRecording = useCallback(makeSetter(dispatch, 'recording'), [dispatch]);
  const setStreaming = useCallback(makeSetter(dispatch, 'streaming'), [dispatch]);
  const setProcessing = useCallback(makeSetter(dispatch, 'processing'), [dispatch]);
  const setPlaying = useCallback(makeSetter(dispatch, 'playing'), [dispatch]);
  const setInterpreterMode = useCallback(makeSetter(dispatch, 'interpreterMode'), [dispatch]);
  const setInstantListening = useCallback(makeSetter(dispatch, 'instantListening'), [dispatch]);
  const setLiveAssistActive = useCallback(makeSetter(dispatch, 'liveAssistActive'), [dispatch]);

  // Convenience: dispatch a coordinated multi-flag transition.
  const setFlags = useCallback((flags) => dispatch({ type: ACTIONS.SET_FLAGS, flags }), [dispatch]);
  const reset = useCallback(() => dispatch({ type: ACTIONS.RESET }), [dispatch]);

  return useMemo(
    () => ({
      // unpacked individual flags
      recording: state.recording,
      streaming: state.streaming,
      processing: state.processing,
      playing: state.playing,
      interpreterMode: state.interpreterMode,
      instantListening: state.instantListening,
      liveAssistActive: state.liveAssistActive,
      // shim setters (drop-in for the original useState setters)
      setRecording,
      setStreaming,
      setProcessing,
      setPlaying,
      setInterpreterMode,
      setInstantListening,
      setLiveAssistActive,
      // new-style API
      setFlags,
      reset,
      dispatch,
    }),
    [state, setRecording, setStreaming, setProcessing, setPlaying, setInterpreterMode, setInstantListening, setLiveAssistActive, setFlags, reset],
  );
}
