/**
 * TranslationStack — AI-recovery banner, source transcript card,
 * translated text card, conversation timeline, and the clarification
 * pill.
 *
 * Extracted from `main.jsx` so the App component's return statement
 * stays under ~80 lines. All state and handlers flow through props.
 */

import React from 'react';
import { Check, Copy, Languages, Radio } from 'lucide-react';

import { compactRepairLabel } from '../utils';

export default function TranslationStack({
  // brain UI / repair chips
  brainUi = {},
  brainModeLabel,
  visibleRepairOptions = [],
  visibleHighlightTerms = [],
  runRepairOption,
  // source card
  hasSourceText,
  transcriptState,
  sourceLanguageLabel,
  sourceText,
  // translated card
  hasTranslatedText,
  translationState,
  targetLanguageLabel,
  translatedText,
  // copy
  copyToClipboard,
  copiedKey,
  // camera / OCR
  cameraActive,
  videoRef,
  ocrText,
  // conversation
  recentConversationTurns = [],
  // clarification
  clarifyVisible,
  clarifyMessage,
  result,
  setClarifyVisible,
  setPipelineStage,
  setStatus,
  haptic,
  streaming,
  processing,
  handleMicClick,
}) {
  const aiRecoveryClass = [
    'ai-recovery',
    brainUi.hints?.language_auto_repaired
      ? 'success'
      : brainUi.hints?.ask_before_speaking || brainUi.skipTts
        ? 'guarded'
        : '',
    brainUi.speakerShift ? 'shift' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <section className="translation-stack">
      {brainUi.visible && (
        <section className={aiRecoveryClass} aria-label="AI recovery">
          <div className="ai-recovery-main">
            <span>{brainUi.message || brainModeLabel || 'Ready'}</span>
            {brainModeLabel && <strong>{brainModeLabel}</strong>}
          </div>
          {brainUi.speakerShift && brainUi.activeSpeakerLabel && (
            <div className="speaker-shift-line" role="status">
              <span>Active speaker</span>
              <strong>{brainUi.activeSpeakerLabel}</strong>
            </div>
          )}
          {(visibleRepairOptions.length > 0 || visibleHighlightTerms.length > 0) && (
            <div className="repair-chip-row">
              {visibleRepairOptions.map((option, index) => (
                <button
                  type="button"
                  key={`${option.type || 'repair'}-${option.word || option.language || index}`}
                  className={option.applied ? 'applied' : ''}
                  onClick={() => runRepairOption(option)}
                >
                  {option.applied && <Check size={13} strokeWidth={2.8} />}
                  <span>{compactRepairLabel(option)}</span>
                </button>
              ))}
              {visibleHighlightTerms.map((term) => (
                <span className="term-chip" key={term}>
                  {term}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      <article
        className={`transcript-card ${hasSourceText ? 'has-text' : ''}`}
        data-state={transcriptState}
      >
        <span className="card-kicker">
          <Radio size={13} strokeWidth={2.5} aria-hidden="true" />
          {sourceLanguageLabel}
        </span>
        <p className="transcript-text fade-in" key={sourceText}>
          {sourceText}
          {transcriptState === 'live' && <span className="live-cursor" aria-hidden="true" />}
        </p>
        {visibleHighlightTerms.length > 0 && (
          <div className="term-row" aria-label="Exact terms">
            {visibleHighlightTerms.map((term) => (
              <span key={term}>{term}</span>
            ))}
          </div>
        )}
        {hasSourceText && (
          <button
            type="button"
            onClick={() => copyToClipboard(sourceText, 'src')}
            aria-label="Copy transcript"
            className={`copy-action ${copiedKey === 'src' ? 'copied' : ''}`}
          >
            {copiedKey === 'src' ? (
              <Check size={15} strokeWidth={2.6} />
            ) : (
              <Copy size={15} strokeWidth={2.4} />
            )}
            <span className="sr-only">
              {copiedKey === 'src' ? 'Copied transcript' : 'Copy transcript'}
            </span>
          </button>
        )}
      </article>

      <article
        className={`translation-card ${hasTranslatedText ? 'has-text' : ''}`}
        data-state={translationState}
      >
        <span className="card-kicker">
          <Languages size={13} strokeWidth={2.5} aria-hidden="true" />
          {targetLanguageLabel}
        </span>
        <p className="translation-text fade-in" key={translatedText}>
          {translatedText}
          {translationState === 'speaking' && (
            <span className="live-cursor voice" aria-hidden="true" />
          )}
        </p>
        {cameraActive && (
          <div className="camera-preview">
            <video ref={videoRef} muted playsInline />
            {ocrText && <p className="transcript-text ocr-text">OCR: {ocrText}</p>}
          </div>
        )}
        {hasTranslatedText && (
          <button
            type="button"
            onClick={() => copyToClipboard(translatedText, 'tr')}
            aria-label="Copy translation"
            className={`copy-action ${copiedKey === 'tr' ? 'copied' : ''}`}
          >
            {copiedKey === 'tr' ? (
              <Check size={15} strokeWidth={2.6} />
            ) : (
              <Copy size={15} strokeWidth={2.4} />
            )}
            <span className="sr-only">
              {copiedKey === 'tr' ? 'Copied translation' : 'Copy translation'}
            </span>
          </button>
        )}
      </article>

      {recentConversationTurns.length > 0 && (
        <section className="conversation-timeline" aria-label="Recent conversation">
          {recentConversationTurns.map((turn) => (
            <article className="conversation-turn" key={turn.id}>
              <strong>{turn.speaker_label}</strong>
              <span>{turn.source_text}</span>
              <em>{turn.translated_text}</em>
            </article>
          ))}
        </section>
      )}

      {(clarifyVisible || result?.clarify || result?.cip_decision?.type === 'clarification') && (
        <div className="clarify-pill" role="status" aria-live="polite">
          <span>{clarifyMessage || result?.clarify_message || 'Clarification requested'}</span>
          <button
            type="button"
            onClick={() => {
              setClarifyVisible(false);
              haptic(20);
              setPipelineStage('Refine requested');
              setStatus('Please rephrase your request');
              if (!streaming && !processing) {
                try {
                  handleMicClick();
                } catch {}
              }
            }}
          >
            Refine phrase
          </button>
        </div>
      )}
    </section>
  );
}
