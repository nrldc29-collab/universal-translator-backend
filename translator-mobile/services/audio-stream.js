/* eslint-disable import/namespace */
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";

let recording = null;
let onChunkCallback = null;
let streamingInterval = null;
let streamingActive = false;
let streamGeneration = 0;
const CHUNK_INTERVAL = 140;

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
    });

    onChunkCallback = onChunk;
    streamingActive = true;
    streamGeneration += 1;
    recordAndSendChunk(streamGeneration);
    
    return true;
  } catch (error) {
    streamingActive = false;
    onError?.(error.message);
    return false;
  }
};

const recordAndSendChunk = async (generation) => {
  if (!streamingActive || generation !== streamGeneration) return;

  let chunkRecording = null;
  try {
    const created = await Audio.Recording.createAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY
    );
    chunkRecording = created.recording;
    
    recording = chunkRecording;
    
    await new Promise(resolve => {
      streamingInterval = setTimeout(resolve, CHUNK_INTERVAL);
    });

    streamingInterval = null;

    if (!streamingActive || generation !== streamGeneration) {
      await stopChunkRecording(chunkRecording);
      return;
    }

    await chunkRecording.stopAndUnloadAsync();
    if (recording === chunkRecording) recording = null;
    const uri = chunkRecording.getURI();
    
    if (uri && onChunkCallback && streamingActive && generation === streamGeneration) {
      const base64 = await FileSystem.readAsStringAsync(uri, {
        encoding: FileSystem.EncodingType.Base64,
      });
      onChunkCallback(base64ToArrayBuffer(base64));
    }
  } catch (error) {
    console.error("Record chunk error:", error);
  } finally {
    if (recording === chunkRecording) recording = null;
    if (streamingActive && generation === streamGeneration) {
      recordAndSendChunk(generation);
    }
  }
};

const stopChunkRecording = async (chunkRecording) => {
  if (!chunkRecording) return;
  try {
    await chunkRecording.stopAndUnloadAsync();
  } catch {
    // The recording may already be unloaded by a concurrent stop.
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
  streamGeneration += 1;

  if (streamingInterval) {
    clearTimeout(streamingInterval);
    streamingInterval = null;
  }

  if (recording) {
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      recording = null;
      return uri;
    } catch (error) {
      console.error("Stop stream error:", error);
      recording = null;
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
      { shouldPlay: true, isMuted: false, volume: 1.0 }
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
