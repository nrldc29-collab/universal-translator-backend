import { useState, useRef } from 'react';
import { fallbackSpeakerLabel } from '../utils';

export function useSpeakerMemory() {
  const [detectedSpeaker, setDetectedSpeaker] = useState('-');
  const speakerLabelsRef = useRef({});

  function rememberSpeaker(data = {}) {
    const speakerId = data.speaker || '';
    const label = data.speaker_label || speakerLabelsRef.current[speakerId] || fallbackSpeakerLabel(speakerId);
    if (speakerId) {
      speakerLabelsRef.current = { ...speakerLabelsRef.current, [speakerId]: label };
    }
    if (label && label !== 'Person') setDetectedSpeaker(label);
    return label;
  }

  function normalizeConversationTurn(turn, index = 0) {
    const speakerId = turn.speaker || '';
    const label = turn.speaker_label || speakerLabelsRef.current[speakerId] || fallbackSpeakerLabel(speakerId);
    if (speakerId) {
      speakerLabelsRef.current = { ...speakerLabelsRef.current, [speakerId]: label };
    }
    return {
      id: `${turn.created_at || Date.now()}-${speakerId || index}-${index}`,
      speaker: speakerId,
      speaker_label: label,
      source_text: turn.source_text || '',
      translated_text: turn.translated_text || '',
      created_at: turn.created_at || Date.now() / 1000,
      lang: turn.source_language || '',
      target_lang: turn.target_language || '',
    };
  }

  function loadSpeakerProfiles(speakers = {}) {
    Object.values(speakers).forEach((profile) => {
      if (profile?.speaker) {
        speakerLabelsRef.current = {
          ...speakerLabelsRef.current,
          [profile.speaker]: profile.speaker_label || fallbackSpeakerLabel(profile.speaker),
        };
      }
    });
  }

  return {
    detectedSpeaker,
    setDetectedSpeaker,
    speakerLabelsRef,
    rememberSpeaker,
    normalizeConversationTurn,
    loadSpeakerProfiles,
  };
}
