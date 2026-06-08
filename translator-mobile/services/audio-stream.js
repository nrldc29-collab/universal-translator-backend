/* eslint-disable import/namespace */
import { Platform } from "react-native";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";

let activeRecording = null;
let onChunkCallback = null;
let streamingActive = false;
let uploadPaused = false;
let streamGeneration = 0;
let utteranceTimer = null;
let meteringInterval = null;

const METERING_POLL_MS = 100;
const VOICE_DB_THRESHOLD = -48;
const METERING_UNAVAILABLE_PEAK = -160;
const SILENCE_MS_TO_FINALIZE = Platform.OS === "ios" ? 900 : 1200;
const MAX_UTTERANCE_MS = Platform.OS === "android" ? 8000 : 15000;
const MIN_UTTERANCE_MS = 700;

const RECORDING_OPTIONS = {
  android: {
    extension: ".m4a",
    outputFormat: Audio.AndroidOutputFormat.MPEG_4,
    audioEncoder: Audio.AndroidAudioEncoder.AAC,
    sampleRate: 44100,
    numberOfChannels: 1,
    bitRate: 128000,
  },
  ios: {
    extension: ".m4a",
    outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
    audioQuality: Audio.IOSAudioQuality.HIGH,
    sampleRate: 44100,
    numberOfChannels: 1,
    bitRate: 128000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  isMeteringEnabled: Platform.OS === "ios",
};

const sleep = (ms) => new Promise((resolve) => {
  utteranceTimer = setTimeout(resolve, ms);
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

export const startAudioStream = async (onChunk, onError) => {
  try {
    if (streamingActive) {
      await stopAudioStream();
    }

    const permission = await Audio.requestPermissionsAsync();
    if (!permission.granted) {
      onError?.("Microphone permission denied");
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
    if (!captured || !streamingActive || generation !== streamGeneration || uploadPaused) {
      continue;
    }

    try {
      onChunkCallback?.(captured.buffer, {
        audioLevel: captured.audioLevel,
        voiceActive: captured.voiceActive,
        meteringAvailable: captured.meteringAvailable,
        finalizeUtterance: true,
        durationMs: captured.durationMs,
      });
    } catch (error) {
      console.error("Utterance upload error:", error);
    }
  }
};

const captureSingleUtterance = async (generation) => {
  let recording = null;
  const peakMetering = { value: METERING_UNAVAILABLE_PEAK };
  let hadSpeech = false;
  let silenceMs = 0;
  const startedAt = Date.now();

  try {
    const created = await Audio.Recording.createAsync(
      RECORDING_OPTIONS,
      undefined,
      RECORDING_OPTIONS.isMeteringEnabled ? METERING_POLL_MS : undefined,
    );
    recording = created.recording;
    activeRecording = recording;

    if (RECORDING_OPTIONS.isMeteringEnabled) {
      meteringInterval = setInterval(async () => {
        if (!recording || !streamingActive || generation !== streamGeneration) return;
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

      const silenceReached = hadSpeech && meteringAvailable && silenceMs >= SILENCE_MS_TO_FINALIZE;
      const maxDurationReached = elapsed >= MAX_UTTERANCE_MS;
      if (silenceReached || (hadSpeech && maxDurationReached)) {
        break;
      }
      if (!meteringAvailable && maxDurationReached) {
        hadSpeech = true;
        break;
      }
    }

    if (!recording || !streamingActive || generation !== streamGeneration || uploadPaused || !hadSpeech) {
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
      : 0.42;

    const base64 = await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
    });
    await FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});

    return {
      buffer: base64ToArrayBuffer(base64),
      audioLevel,
      voiceActive: true,
      meteringAvailable,
      durationMs: Date.now() - startedAt,
    };
  } catch (error) {
    console.error("Utterance capture error:", error);
    await unloadRecording(recording);
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
      console.error("Stop stream error:", error);
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
    console.error("TTS playback error:", error);
    return false;
  }
};
