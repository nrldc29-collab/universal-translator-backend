/**
 * TranslationStack - AI-recovery banner, source transcript card,
 * translated text card, conversation timeline, and the clarification
 * pill.
 *
 * Extracted from `main.jsx` so the App component's return statement
 * stays under ~80 lines. All state and handlers flow through props.
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { ArrowRight, Check, Copy, Keyboard, Languages, Loader2, Mic, Radio, Share2, Sparkles, X } from 'lucide-react';

import { compactRepairLabel } from '../utils';
import TypingText from './TypingText';
import LanguageFlag from './LanguageFlag';
import ConversationActions from './ConversationActions';

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
  sourceLanguageCode,
  sourceText,
  // translated card
  hasTranslatedText,
  translationState,
  targetLanguageLabel,
  targetLanguageCode,
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
  onClearConversation,
  // clarification
  clarifyVisible,
  clarifyMessage,
  confidenceWarningVisible,
  confidenceWarningMessage,
  setConfidenceWarningVisible,
  result,
  setClarifyVisible,
  setPipelineStage,
  setStatus,
  haptic,
  streaming,
  processing,
  handleMicClick,
  // typing animation
  enableTypingAnimation = true,
  isTranslationActive = false,
  // text-input translate
  textTranslateReady = true,
  onTextTranslate,
  textInputMode: textInputModeProp,
  onTextInputModeChange,
  connectionStatus = 'online',
  isTextTranslating = false,
  onNotify,
  onOpenSettings,
  onOfflineRetry,
}) {
  const [typingComplete, setTypingComplete] = useState(false);
  const [localTextInputMode, setLocalTextInputMode] = useState(false);
  const textInputMode = textInputModeProp ?? localTextInputMode;
  const setTextInputMode = onTextInputModeChange ?? setLocalTextInputMode;
  const [textInputValue, setTextInputValue] = useState('');
  const textareaRef = useRef(null);
  const MAX_CHARS = 400;
  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function';
  const showEmptyTips = !hasSourceText && !hasTranslatedText && !textInputMode && !brainUi.visible;

  useEffect(() => {
    if (textInputMode) {
      setTimeout(() => textareaRef.current?.focus(), 40);
    } else {
      setTextInputValue('');
    }
  }, [textInputMode]);

  const handleTextSubmit = useCallback(() => {
    const trimmed = textInputValue.trim();
    if (!trimmed || !onTextTranslate || !textTranslateReady || isTextTranslating) return;
    onTextTranslate(trimmed);
  }, [textInputValue, onTextTranslate, textTranslateReady, isTextTranslating]);

  const handleTextKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTextSubmit();
    }
    if (e.key === 'Escape') setTextInputMode(false);
  }, [handleTextSubmit, setTextInputMode]);

  const shareText = useCallback(async (text, label) => {
    const trimmed = String(text || '').trim();
    if (!trimmed) return;
    if (canShare) {
      try {
        await navigator.share({ title: label, text: trimmed });
        onNotify?.('Shared', 'success');
      } catch {
        // User cancelled
      }
      return;
    }
    copyToClipboard(trimmed, label === 'Translation' ? 'tr' : 'src');
  }, [canShare, copyToClipboard, onNotify]);
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
    <section className="translation-stack" id="main-content">

      {showEmptyTips && (
        <div className="empty-state translation-empty-state" data-connection={connectionStatus} aria-live="polite">
          <div className="empty-state-icon">
            <Sparkles size={26} strokeWidth={1.8} />
          </div>
          <h3 className="empty-state-title">Ready when you are</h3>
          <p className="empty-state-description">
            {connectionStatus === 'online'
              ? 'Tap the microphone to speak, or use Type to enter text manually.'
              : connectionStatus === 'checking' || connectionStatus === 'warming'
                ? 'Hang tight — we are getting the translator ready for you.'
                : 'Connect to the server, then tap the mic to start translating.'}
          </p>
          <div className="empty-state-tips">
            <span className="empty-state-tip">
              <Languages size={14} strokeWidth={2.2} />
              Pick languages above
            </span>
            <span className="empty-state-tip">
              <Keyboard size={14} strokeWidth={2.2} />
              Type instead of speaking
            </span>
          </div>
          <div className="empty-state-actions">
            {connectionStatus === 'online' ? (
              <>
                <button
                  type="button"
                  className="empty-state-cta primary"
                  onClick={handleMicClick}
                >
                  <Mic size={15} strokeWidth={2.4} />
                  Start speaking
                </button>
                <button
                  type="button"
                  className="empty-state-cta"
                  onClick={() => setTextInputMode(true)}
                >
                  <Keyboard size={15} strokeWidth={2.4} />
                  Type to translate
                </button>
              </>
            ) : (
              <>
                <button type="button" className="empty-state-cta primary" onClick={onOpenSettings}>
                  Open settings
                </button>
                {onOfflineRetry && (
                  <button type="button" className="empty-state-cta" onClick={onOfflineRetry}>
                    Retry connection
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {textInputMode && (
        <div className="text-input-card">
          <div className="text-input-header">
            <span className="text-input-label">
              <Keyboard size={11} strokeWidth={2.5} />
              Type to translate
            </span>
            <button
              type="button"
              className="text-input-close"
              aria-label="Close text input"
              onClick={() => { setTextInputMode(false); setTextInputValue(''); }}
            >
              <X size={14} strokeWidth={2.2} />
            </button>
          </div>
          <textarea
            ref={textareaRef}
            className="text-input-field"
            value={textInputValue}
            onChange={e => setTextInputValue(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={handleTextKeyDown}
            placeholder="Enter text to translate…"
            rows={3}
            disabled={isTextTranslating}
            aria-busy={isTextTranslating}
          />
          <div className="text-input-actions">
            <span
              className={[
                'text-input-char-count',
                textInputValue.length >= MAX_CHARS ? 'at-limit' : '',
                textInputValue.length > 350 ? 'near-limit' : '',
              ].filter(Boolean).join(' ')}
            >
              {textInputValue.length}/{MAX_CHARS}
            </span>
            <button
              type="button"
              className={`text-input-submit${isTextTranslating ? ' loading' : ''}`}
              disabled={!textTranslateReady || !textInputValue.trim() || isTextTranslating}
              onClick={handleTextSubmit}
            >
              {isTextTranslating ? (
                <Loader2 size={14} strokeWidth={2.5} className="spin-icon" />
              ) : (
                <ArrowRight size={13} strokeWidth={2.5} />
              )}
              {isTextTranslating ? 'Translating…' : 'Translate'}
            </button>
          </div>
        </div>
      )}

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

      {!showEmptyTips && (
      <article
        className={`transcript-card ${hasSourceText ? 'has-text' : ''} ${textInputMode ? 'hidden' : ''}`}
        data-state={transcriptState}
      >
        <span className="card-kicker">
          <Radio size={13} strokeWidth={2.5} aria-hidden="true" />
          <LanguageFlag
            languageCode={sourceLanguageCode}
            size="small"
            isActive={transcriptState === 'live'}
            isSource={true}
          />
          {sourceLanguageLabel}
        </span>
        <p className="transcript-text fade-in" key={sourceText}>
          {enableTypingAnimation && transcriptState === 'live' ? (
            <TypingText
              text={sourceText}
              isActive={true}
              typingSpeed={20}
              highlightWords={false}
            />
          ) : (
            sourceText
          )}
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
          <div className="card-actions">
            {canShare && (
              <button
                type="button"
                onClick={() => shareText(sourceText, 'Transcript')}
                aria-label="Share transcript"
                className="copy-action"
              >
                <Share2 size={15} strokeWidth={2.4} />
              </button>
            )}
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
          </div>
        )}
      </article>
      )}

      {!showEmptyTips && (
      <article
        className={`translation-card ${hasTranslatedText ? 'has-text' : ''} ${(processing || isTextTranslating) && !hasTranslatedText ? 'is-busy' : ''}`}
        data-state={translationState}
        aria-busy={(processing || isTextTranslating) && !hasTranslatedText}
      >
        <span className="card-kicker">
          <Languages size={13} strokeWidth={2.5} aria-hidden="true" />
          <LanguageFlag
            languageCode={targetLanguageCode}
            size="small"
            isActive={translationState === 'speaking' || isTranslationActive}
            isTarget={true}
          />
          {targetLanguageLabel}
        </span>
        <p className="translation-text fade-in" key={translatedText}>
          {enableTypingAnimation && isTranslationActive && !typingComplete ? (
            <TypingText
              text={translatedText}
              isActive={true}
              typingSpeed={25}
              highlightWords={true}
              languageCode={targetLanguageCode}
              onComplete={() => setTypingComplete(true)}
            />
          ) : (
            translatedText
          )}
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
          <div className="card-actions">
            {canShare && (
              <button
                type="button"
                onClick={() => shareText(translatedText, 'Translation')}
                aria-label="Share translation"
                className="copy-action"
              >
                <Share2 size={15} strokeWidth={2.4} />
              </button>
            )}
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
            </button>
          </div>
        )}
      </article>
      )}

      {confidenceWarningVisible && confidenceWarningMessage && (
        <div className="confidence-warning-pill" role="status">
          <span className="confidence-warning-text">{confidenceWarningMessage}</span>
          <div className="clarify-pill-actions">
            <button
              type="button"
              className="clarify-no"
              onClick={() => setConfidenceWarningVisible(false)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {clarifyVisible && clarifyMessage && (
        <div className="clarify-pill" role="alert">
          <span className="clarify-pill-text">{clarifyMessage}</span>
          <div className="clarify-pill-actions">
            <button
              type="button"
              className="clarify-yes"
              onClick={() => {
                setClarifyVisible(false);
                setPipelineStage?.('Listening');
                setStatus?.('Ready to listen');
                handleMicClick?.();
                haptic?.(20);
              }}
            >
              Speak again
            </button>
            <button
              type="button"
              className="clarify-no"
              onClick={() => setClarifyVisible(false)}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {recentConversationTurns.length > 0 && (
        <div className="conversation-history">
          <div className="conversation-history-header">
            <span className="conversation-history-count">
              {recentConversationTurns.length} exchange{recentConversationTurns.length !== 1 ? 's' : ''}
            </span>
            <ConversationActions
              conversationTurns={recentConversationTurns}
              onClear={onClearConversation}
              onCopy={(text) => copyToClipboard(text, 'conversation')}
              disabled={streaming || processing}
            />
          </div>
          <div className="conversation-turns-list">
            {recentConversationTurns.map((turn, i) => (
              <div
                key={`${turn.timestamp || i}-${i}`}
                className={`conversation-turn${i === recentConversationTurns.length - 1 ? ' latest' : ''}`}
              >
                <div className="turn-meta">
                  <span>{turn.speaker_label || (turn.conversationSpeaker === 'B' ? 'Person 2' : 'Person 1')}</span>
                  {turn.timestamp && (
                    <span>{new Date(turn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  )}
                </div>
                {turn.source_text && <p className="turn-source">{turn.source_text}</p>}
                {turn.translated_text && <p className="turn-translation">{turn.translated_text}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
