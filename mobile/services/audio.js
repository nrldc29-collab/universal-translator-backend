import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

let recording = null;
let running = false;
let ttsQueue = [];
let ttsPlaying = false;

export async function startMic(onChunk, chunkMs = 500) {
  const permission = await Audio.requestPermissionsAsync();
  if (!permission.granted) {
    throw new Error('Microphone permission denied');
  }

  await Audio.setAudioModeAsync({
    allowsRecordingIOS: true,
    playsInSilentModeIOS: true,
    staysActiveInBackground: false,
  });

  running = true;

  async function recordLoop() {
    if (!running) return;

    recording = new Audio.Recording();
    await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    await recording.startAsync();
    await new Promise((resolve) => setTimeout(resolve, chunkMs));
    await recording.stopAndUnloadAsync();

    const uri = recording.getURI();
    recording = null;

    if (uri && running) {
      const response = await fetch(uri);
      const audioChunk = await response.arrayBuffer();
      await onChunk(audioChunk, uri);
      await FileSystem.deleteAsync(uri, { idempotent: true });
    }

    if (running) recordLoop();
  }

  recordLoop();
}

export async function stopMic() {
  running = false;
  try {
    await recording?.stopAndUnloadAsync();
  } catch {}
  recording = null;
}

export async function playAudio(base64, mimeType = 'audio/wav') {
  ttsQueue.push({ base64, mimeType });
  if (ttsPlaying) return;
  await playNextQueuedAudio();
}

async function playNextQueuedAudio() {
  const next = ttsQueue.shift();
  if (!next) {
    ttsPlaying = false;
    return;
  }

  ttsPlaying = true;
  const { base64, mimeType } = next;
  const extension = mimeType.includes('mpeg') || mimeType.includes('mp3') ? 'mp3' : 'wav';
  const uri = `${FileSystem.cacheDirectory}tts-${Date.now()}.${extension}`;

  await FileSystem.writeAsStringAsync(uri, base64, {
    encoding: FileSystem.EncodingType.Base64,
  });

  await Audio.setAudioModeAsync({
    allowsRecordingIOS: false,
    playsInSilentModeIOS: true,
  });

  const { sound } = await Audio.Sound.createAsync({ uri });
  sound.setOnPlaybackStatusUpdate((state) => {
    if (state.didJustFinish) {
      sound.unloadAsync();
      FileSystem.deleteAsync(uri, { idempotent: true });
      playNextQueuedAudio();
    }
  });
  await sound.playAsync();
}
