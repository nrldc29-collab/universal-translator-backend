import { Audio } from "expo-av";

export const AUDIO_QUALITY_KEY = "audio_quality";
export const LOW_BANDWIDTH_KEY = "low_bandwidth_mode";

export const AUDIO_QUALITIES = {
  LOW: {
    label: "Low",
    description: "Smaller chunks, faster on slow Wi‑Fi",
    bitRate: 64000,
    iosQuality: Audio.IOSAudioQuality.LOW,
  },
  MEDIUM: {
    label: "Medium",
    description: "Balanced quality and upload size",
    bitRate: 96000,
    iosQuality: Audio.IOSAudioQuality.MEDIUM,
  },
  HIGH: {
    label: "High",
    description: "Best clarity for speech recognition",
    bitRate: 128000,
    iosQuality: Audio.IOSAudioQuality.HIGH,
  },
};

export function buildRecordingOptions(qualityKey = "HIGH") {
  const quality = AUDIO_QUALITIES[qualityKey] || AUDIO_QUALITIES.HIGH;
  return {
    android: {
      extension: ".m4a",
      outputFormat: Audio.AndroidOutputFormat.MPEG_4,
      audioEncoder: Audio.AndroidAudioEncoder.AAC,
      sampleRate: 44100,
      numberOfChannels: 1,
      bitRate: quality.bitRate,
    },
    ios: {
      extension: ".m4a",
      outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
      audioQuality: quality.iosQuality,
      sampleRate: 44100,
      numberOfChannels: 1,
      bitRate: quality.bitRate,
      linearPCMBitDepth: 16,
      linearPCMIsBigEndian: false,
      linearPCMIsFloat: false,
    },
    isMeteringEnabled: true,
  };
}
