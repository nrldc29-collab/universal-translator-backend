import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";

let recording = null;
let onChunkCallback = null;
let streamingInterval = null;
const CHUNK_INTERVAL = 500; // ms between chunks (500ms = good balance)

export const startAudioStream = async (onChunk, onError) => {
  try {
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
    
    // Start the chunk recording loop
    await recordAndSendChunk();
    
    return true;
  } catch (error) {
    onError?.(error.message);
    return false;
  }
};

const recordAndSendChunk = async () => {
  try {
    // Record a short chunk
    const { recording: chunkRecording } = await Audio.Recording.createAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY
    );
    
    recording = chunkRecording;
    
    // Wait for the chunk interval
    await new Promise(resolve => {
      streamingInterval = setTimeout(async () => {
        try {
          await chunkRecording.stopAndUnloadAsync();
          const uri = chunkRecording.getURI();
          
          if (uri && onChunkCallback) {
            const base64 = await FileSystem.readAsStringAsync(uri, {
              encoding: FileSystem.EncodingType.Base64,
            });
            onChunkCallback(base64ToArrayBuffer(base64));
          }
        } catch (e) {
          console.error("Chunk send error:", e);
        }
        
        // Start next chunk if still streaming
        if (streamingInterval) {
          recordAndSendChunk();
        }
        
        resolve();
      }, CHUNK_INTERVAL);
    });
  } catch (error) {
    console.error("Record chunk error:", error);
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

    const { sound } = await Audio.Sound.createAsync(
      { uri },
      { shouldPlay: true }
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