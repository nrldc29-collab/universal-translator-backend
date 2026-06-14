import { Platform } from "react-native";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system/legacy";
import { buildRecordingOptions } from "../constants/audioQuality";
import { mobileError } from "../utils/mobileLogger";

let activeRecording = null;
let onChunkCallback = null;
let onStreamErrorCallback = null;
let onVoiceActivityCallback = null;
let streamingActive = false;
let uploadPaused = false;
let streamGeneration = 0;
let utteranceTimer = null;
let meteringInterval = null;

const METERING_POLL_MS = 100;
const VOICE_DB_THRESHOLD = Platform.OS === "ios" ? -62 : -52;
const METERING_UNAVAILABLE_PEAK = -160;
const SILENCE_MS_TO_FINALIZE = Platform.OS === "ios" ? 700 : 900;
const MAX_UTTERANCE_MS = Platform.OS === "android" ? 8000 : 15000;
const MIN_UTTERANCE_MS = Platform.OS === "ios" ? 900 : 700;
const OPEN_MIC_FALLBACK_MS = Platform.OS === "ios" ? 2200 : 3000;

let activeQualityKey = "HIGH";

export const setAudioStreamQuality = (qualityKey = "HIGH") => {
  activeQualityKey = qualityKey;
};

const getRecordingOptions = () => buildRecordingOptions(activeQualityKey);

const sleep = (ms) => new Promise((resolve) => {
  setTimeout(resolve, ms);
});

const clearUtteranceTimer = () => {
  if (utteranceTimer) {
    clearTimeout(utteranceTimer);
    utteranceTimer = null;
  }
};

const clearMeteringPoll = () => {
  if (meteringInterval) {
    clearInterval(meteringInterval);
    meteringInterval = null;
  }
};

export const pauseAudioUpload = () => {
  uploadPaused = true;
};

export const resumeAudioUpload = () => {
  uploadPaused = false;
};

export const restoreRecordingAudioMode = async () => {
  await Audio.setAudioModeAsync({
    allowsRecordingIOS: true,
    playsInSilentModeIOS: true,
    staysActiveInBackground: false,
    shouldDuckAndroid: true,
    playThroughEarpieceAndroid: false,
  });
};

export const isAudioUploadPaused = () => uploadPaused;

export const startAudioStream = async (onChunk, onError, onVoiceActivity) => {
  try {
    if (streamingActive) {
      await stopAudioStream();
    }

    const existing = await Audio.getPermissionsAsync();
    const permission = existing.granted
      ? existing
      : await Audio.requestPermissionsAsync();
    if (!permission.granted) {
      onError?.(permission.canAskAgain === false
        ? "Microphone blocked — enable in Settings"
        : "Microphone permission denied");
      return false;
    }

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
      staysActiveInBackground: false,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    });

    onChunkCallback = onChunk;
    onStreamErrorCallback = onError;
    onVoiceActivityCallback = onVoiceActivity || null;
    streamingActive = true;
    uploadPaused = false;
    streamGeneration += 1;
    captureUtteranceLoop(streamGeneration);

    return true;
  } catch (error) {
    streamingActive = false;
    onError?.(error.message);
    return false;
  }
};

const captureUtteranceLoop = async (generation) => {
  while (streamingActive && generation === streamGeneration) {
    if (uploadPaused) {
      await sleep(180);
      continue;
    }

    const captured = await captureSingleUtterance(generation);
    if (captured?.fatal) {
      streamingActive = false;
      onStreamErrorCallback?.(captured.fatal);
      break;
    }
    if (!captured || !streamingActive || generation !== streamGeneration || uploadPaused) {
      continue;
    }

    try {
      if (!onChunkCallback) continue;
      onChunkCallback(captured.buffer, {
        audioLevel: captured.audioLevel,
        voiceActive: captured.voiceActive,
        meteringAvailable: captured.meteringAvailable,
        finalizeUtterance: true,
        durationMs: captured.durationMs,
      });
    } catch (error) {
      mobileError("Utterance upload error:", error, { expected: true });
    }
  }
};

const captureSingleUtterance = async (generation) => {
  let recording = null;
  const peakMetering = { value: METERING_UNAVAILABLE_PEAK };
  let hadSpeech = false;
  let silenceMs = 0;
  let lastVoiceActivitySent = 0;
  const startedAt = Date.now();

  try {
    const recordingOptions = getRecordingOptions();
    const created = await Audio.Recording.createAsync(
      recordingOptions,
      undefined,
      recordingOptions.isMeteringEnabled ? METERING_POLL_MS : undefined,
    );
    recording = created.recording;
    activeRecording = recording;

    if (recordingOptions.isMeteringEnabled) {
      meteringInterval = setInterval(async () => {
        if (!recording || !streamingActive || uploadPaused || generation !== streamGeneration) return;
        try {
          const status = await recording.getStatusAsync();
          const metering = Number(status.metering);
          if (Number.isFinite(metering) && metering > peakMetering.value) {
            peakMetering.value = metering;
          }
        } catch {
          // Recording may have stopped between polls.
        }
      }, METERING_POLL_MS);
    }

    while (streamingActive && generation === streamGeneration && !uploadPaused) {
      await sleep(METERING_POLL_MS);
      const elapsed = Date.now() - startedAt;
      if (elapsed < MIN_UTTERANCE_MS) continue;

      const meteringAvailable = peakMetering.value > METERING_UNAVAILABLE_PEAK + 1;
      const voiceNow = meteringAvailable
        ? peakMetering.value >= VOICE_DB_THRESHOLD
        : elapsed < MAX_UTTERANCE_MS - 250;

      if (voiceNow) {
        hadSpeech = true;
        silenceMs = 0;
      } else if (hadSpeech && meteringAvailable) {
        silenceMs += METERING_POLL_MS;
      } else if (!meteringAvailable && elapsed >= MAX_UTTERANCE_MS - 250) {
        hadSpeech = true;
      }

      if (onVoiceActivityCallback && Date.now() - lastVoiceActivitySent >= 250) {
        lastVoiceActivitySent = Date.now();
        const liveLevel = meteringAvailable
          ? Math.max(0, Math.min(1, (peakMetering.value + 60) / 60))
          : 0;
        try {
          onVoiceActivityCallback({
            audioLevel: liveLevel,
            voiceActive: voiceNow,
            heartbeat: true,
          });
        } catch {
          // Voice-activity hook must not break capture.
        }
      }

      const strongVoice = meteringAvailable && peakMetering.value >= VOICE_DB_THRESHOLD + 10;
      const adaptiveSilenceMs = strongVoice
        ? Math.max(MIN_UTTERANCE_MS, SILENCE_MS_TO_FINALIZE - 320)
        : (meteringAvailable && peakMetering.value >= VOICE_DB_THRESHOLD + 5
          ? Math.max(MIN_UTTERANCE_MS, SILENCE_MS_TO_FINALIZE - 200)
          : SILENCE_MS_TO_FINALIZE);
      const silenceReached = hadSpeech && meteringAvailable && silenceMs >= adaptiveSilenceMs;
      const maxDurationReached = elapsed >= MAX_UTTERANCE_MS;
      if (meteringAvailable && !hadSpeech && elapsed >= OPEN_MIC_FALLBACK_MS) {
        hadSpeech = true;
      }
      if (silenceReached || (hadSpeech && maxDurationReached) || maxDurationReached) {
        if (elapsed >= MIN_UTTERANCE_MS) {
          hadSpeech = true;
        }
        break;
      }
    }

    if (!recording || !streamingActive || generation !== streamGeneration || uploadPaused) {
      await unloadRecording(recording);
      return null;
    }

    if (!hadSpeech) {
      try {
        const status = await recording.getStatusAsync();
        if (Number(status?.durationMillis || 0) >= MIN_UTTERANCE_MS) {
          hadSpeech = true;
        }
      } catch {
        // Fall through to unload when no usable audio was captured.
      }
    }

    if (!hadSpeech) {
      await unloadRecording(recording);
      return null;
    }

    await recording.stopAndUnloadAsync();
    if (activeRecording === recording) activeRecording = null;

    const uri = recording.getURI();
    if (!uri) return null;

    const meteringAvailable = peakMetering.value > METERING_UNAVAILABLE_PEAK + 1;
    const audioLevel = meteringAvailable
      ? Math.max(0, Math.min(1, (peakMetering.value + 60) / 60))
      : 0.28;

    const base64 = await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
    });
    await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});

    const audioBuffer = base64ToArrayBuffer(base64);
    return {
      buffer: audioBuffer,
      byteLength: audioBuffer.byteLength,
      audioLevel,
      voiceActive: hadSpeech,
      meteringAvailable,
      durationMs: Date.now() - startedAt,
    };
  } catch (error) {
    mobileError("Utterance capture error:", error, { expected: true });
    await unloadRecording(recording);
    const message = String(error?.message || error || "Microphone error");
    if (/permission|denied|record|audio/i.test(message)) {
      return { fatal: message };
    }
    return null;
  } finally {
    clearMeteringPoll();
    if (activeRecording === recording) activeRecording = null;
  }
};

const unloadRecording = async (recording) => {
  if (!recording) return;
  try {
    const uri = recording.getURI();
    await recording.stopAndUnloadAsync();
    if (uri) {
      await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
    }
  } catch {
    // Recording may already be unloaded.
  }
};

const base64ToArrayBuffer = (base64) => {
  const binary = globalThis.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
};

export const stopAudioStream = async () => {
  streamingActive = false;
  uploadPaused = false;
  onChunkCallback = null;
  onStreamErrorCallback = null;
  onVoiceActivityCallback = null;
  streamGeneration += 1;
  clearUtteranceTimer();
  clearMeteringPoll();

  if (activeRecording) {
    try {
      const uri = activeRecording.getURI();
      await activeRecording.stopAndUnloadAsync();
      activeRecording = null;
      if (uri) {
        await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
      }
      return uri;
    } catch (error) {
      mobileError("Stop stream error:", error, { expected: true });
      activeRecording = null;
      return null;
    }
  }
  return null;
};

export const playTtsAudio = async (audioBase64, mimeType = "audio/wav") => {
  try {
    const extension = mimeType.includes("mpeg") || mimeType.includes("mp3") ? "mp3" : "wav";
    const uri = `${FileSystem.cacheDirectory}tts-${Date.now()}.${extension}`;
    await FileSystem.writeAsStringAsync(uri, audioBase64, {
      encoding: FileSystem.EncodingType.Base64,
    });

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      staysActiveInBackground: false,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    });

    const { sound } = await Audio.Sound.createAsync(
      { uri },
      { shouldPlay: true, isMuted: false, volume: 1.0 },
    );

    sound.setOnPlaybackStatusUpdate((playbackStatus) => {
      if (playbackStatus.didJustFinish) {
        sound.unloadAsync();
        FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
      }
    });

    return true;
  } catch (error) {
    mobileError("TTS playback error:", error, { expected: true });
    return false;
  }
};
