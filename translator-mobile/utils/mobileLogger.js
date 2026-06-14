/** Verbose mobile diagnostics (set EXPO_PUBLIC_DEBUG_LOGS=1). Not tied to __DEV__ for a clean Expo console. */
function isVerboseEnabled() {
  return process.env.EXPO_PUBLIC_DEBUG_LOGS === "1";
}

export function isMobileVerbose() {
  return isVerboseEnabled();
}

/** Hide known third-party warnings that do not affect app behavior in Expo Go. */
export function configureMobileLogBox() {
  try {
    const { LogBox } = require("react-native");
    LogBox.ignoreLogs([
      "SafeAreaView has been deprecated",
      "Non-serializable values were found in the navigation state",
      "[expo-av]: Expo AV has been deprecated",
      "new NativeEventEmitter",
      "Require cycle:",
      "ViewPropTypes will be removed",
      "Sending `onAnimatedValueUpdate`",
      "VirtualizedLists should never be nested",
      "WebSocket error",
      "Network request failed",
      "Unable to deserialize cloned data",
      "Bootstrap discovery timed out",
      "Possible Unhandled Promise Rejection",
      "Task orphaned",
    ]);
  } catch {
    // LogBox unavailable in some test environments.
  }
}

const QUIET_CONSOLE_ERROR =
  /WebSocket error|Auto-login failed|Bootstrap gate failed|Network request failed|Failed to fetch|Login failed|TTS playback|Utterance (upload|capture)|Queued send error|Heartbeat send error|Message parse error|Send error|Anai startup error|Error stopping mic|Error resuming mic|Error pausing mic|Tunnel refresh failed|Remote server fallback failed|Network check error|Server discovery failed|Error loading stored|Upload attempt \d+ failed|401|Unauthorized|Cloud sign-in|Cloud login|Task orphaned|AbortError|aborted/i;

const QUIET_CONSOLE_WARN =
  /SafeAreaView has been deprecated|expo-av|NativeEventEmitter|Require cycle|ViewPropTypes|VirtualizedLists should never be nested|Sending `onAnimatedValueUpdate`|Non-serializable values were found/i;

/** LogBox + filter transient console.error noise when not in verbose mode. */
export function configureMobileRuntime() {
  configureMobileLogBox();
  if (isVerboseEnabled()) return;
  if (global.__anaiQuietConsole) return;
  global.__anaiQuietConsole = true;
  const originalError = console.error.bind(console);
  console.error = (...args) => {
    const msg = args
      .map((arg) => (arg instanceof Error ? arg.message : String(arg ?? "")))
      .join(" ");
    if (QUIET_CONSOLE_ERROR.test(msg)) return;
    originalError(...args);
  };
  const originalWarn = console.warn.bind(console);
  console.warn = (...args) => {
    const msg = args
      .map((arg) => (arg instanceof Error ? arg.message : String(arg ?? "")))
      .join(" ");
    if (QUIET_CONSOLE_WARN.test(msg)) return;
    originalWarn(...args);
  };
}

export function mobileDebug(...args) {
  if (isVerboseEnabled()) console.debug(...args);
}

export function mobileWarn(...args) {
  if (isVerboseEnabled()) console.warn(...args);
}

/** Log errors; mark `expected` for transient auth/WS/network noise when not in verbose mode. */
export function mobileError(label, error, { expected = false } = {}) {
  const detail = error?.message || error || "";
  if (expected && !isVerboseEnabled()) {
    return;
  }
  if (expected && isVerboseEnabled()) {
    mobileDebug(label, detail);
    return;
  }
  if (detail) {
    console.error(label, detail);
  } else {
    console.error(label);
  }
}
