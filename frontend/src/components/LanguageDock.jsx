/**
 * LanguageDock — compact language pair + bottom-sheet picker (speech-first layout).
 */
import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeftRight, ChevronDown, Check, Search, X } from 'lucide-react';
import { TARGET_LANGUAGE_OPTIONS } from '../utils';
import { languagePickerTitle, routeCaptions } from '../utils/productVoice';

function LangPickerSheet({ value, onChange, onClose, variant }) {
  const [query, setQuery] = useState('');
  const searchRef = useRef(null);
  const isTarget = variant === 'target';

  const options = query.trim()
    ? TARGET_LANGUAGE_OPTIONS.filter((o) =>
        o.label.toLowerCase().includes(query.toLowerCase()) ||
        (o.native && o.native.toLowerCase().includes(query.toLowerCase())) ||
        o.code.toLowerCase().includes(query.toLowerCase()),
      )
    : TARGET_LANGUAGE_OPTIONS;

  useEffect(() => {
    const prevHtmlOverflow = document.documentElement.style.overflow;
    const prevBodyOverflow = document.body.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    const t = setTimeout(() => searchRef.current?.focus(), 50);
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => {
      document.documentElement.style.overflow = prevHtmlOverflow;
      document.body.style.overflow = prevBodyOverflow;
      clearTimeout(t);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return createPortal(
    <>
      <div className="lang-picker-overlay" onClick={onClose} role="presentation" aria-hidden="true" />
      <div
        className={`lang-picker-sheet ${isTarget ? 'target' : 'source'}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={isTarget ? 'Choose who hears' : 'Choose you speak language'}
      >
        <div className="lang-picker-grab" aria-hidden="true" />
        <div className="lang-picker-header">
          <span className="lang-picker-title">
            {languagePickerTitle(isTarget ? 'target' : 'source')}
          </span>
          <button type="button" className="lang-picker-close" onClick={onClose} aria-label="Close">
            <X size={16} strokeWidth={2.2} />
          </button>
        </div>
        <div className="lang-search-row">
          <Search size={12} strokeWidth={2.5} className="lang-search-icon" />
          <input
            ref={searchRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search all 14 languages…"
            className="lang-search-input"
          />
          {query && (
            <button type="button" className="lang-search-clear" onClick={() => setQuery('')}>×</button>
          )}
        </div>
        <div className="lang-picker-list" role="listbox">
          {options.length === 0 && (
            <p className="lang-dropdown-empty" role="status">
              No languages match &ldquo;{query.trim()}&rdquo;
            </p>
          )}
          {options.map((opt) => {
            const sel = opt.code === value;
            return (
              <button
                key={opt.code}
                type="button"
                role="option"
                aria-selected={sel}
                onClick={() => { onChange(opt.code); onClose(); }}
                className={`lang-option ${sel ? 'selected' : ''}`}
              >
                <span className="lang-option-flag">{opt.flag}</span>
                <div className="lang-option-text">
                  <div className={`lang-option-name ${sel ? 'selected' : ''}`}>{opt.label}</div>
                  {opt.native && opt.native !== opt.label && (
                    <div className="lang-option-native">{opt.native}</div>
                  )}
                </div>
                {sel && <Check size={13} color="#34d399" />}
              </button>
            );
          })}
        </div>
      </div>
    </>,
    document.body,
  );
}

function LangChip({ value, onOpen, disabled, variant = 'target' }) {
  const current = TARGET_LANGUAGE_OPTIONS.find((o) => o.code === value);
  const isTarget = variant === 'target';

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onOpen}
      aria-haspopup="dialog"
      className={`lang-dropdown-trigger ${isTarget ? 'target' : 'source'}`}
    >
      <span className="lang-dropdown-flag">{current?.flag || '🌐'}</span>
      <span className={`lang-dropdown-label ${isTarget ? 'target' : ''}`}>
        {current?.label || value}
      </span>
      <ChevronDown size={13} strokeWidth={2.2} className="lang-dropdown-chevron" />
    </button>
  );
}

export default function LanguageDock({
  sourceLanguageLabel,
  targetLanguageLabel,
  sourceLanguage,
  targetLanguage,
  setSourceLanguage,
  setTargetLanguage,
  recording,
  processing,
  streaming = false,
  brainUi = {},
  quickActions = [],
}) {
  const disabled = recording;
  const [flipped, setFlipped] = useState(false);
  const [picker, setPicker] = useState(null);
  const captions = routeCaptions(true);

  return (
    <section className="language-dock" data-tour-target="languages" aria-label="Conversation bridge languages">
      <div className="lang-dock-row">
        <div className="lang-dock-slot">
          <span className="lang-dock-role">{captions.source}</span>
          {setSourceLanguage ? (
            <LangChip
              value={sourceLanguage}
              onOpen={() => setPicker('source')}
              disabled={disabled}
              variant="source"
            />
          ) : (
            <div className="lang-static-chip">
              <span className="lang-static-label">{sourceLanguageLabel}</span>
            </div>
          )}
        </div>

        <button
          type="button"
          disabled={disabled}
          aria-label="Swap bridge direction"
          className={`lang-swap-btn${streaming ? ' is-bridging' : ''}`}
          onClick={() => {
            if (disabled) return;
            setFlipped((f) => !f);
            if (setSourceLanguage) setSourceLanguage(targetLanguage);
            setTargetLanguage(sourceLanguage);
          }}
        >
          <ArrowLeftRight
            size={13}
            strokeWidth={2.5}
            className={`lang-swap-icon ${flipped ? 'flipped' : ''}`}
          />
        </button>

        <div className="lang-dock-slot">
          <span className="lang-dock-role">{captions.target}</span>
          <LangChip
            value={targetLanguage}
            onOpen={() => setPicker('target')}
            disabled={disabled}
            variant="target"
          />
        </div>
      </div>

      {picker === 'source' && setSourceLanguage && (
        <LangPickerSheet
          value={sourceLanguage}
          onChange={setSourceLanguage}
          onClose={() => setPicker(null)}
          variant="source"
        />
      )}
      {picker === 'target' && (
        <LangPickerSheet
          value={targetLanguage}
          onChange={setTargetLanguage}
          onClose={() => setPicker(null)}
          variant="target"
        />
      )}

      {quickActions.length > 0 && (
        <div className="quick-actions" aria-label="Quick actions">
          {quickActions.map((action) => (
            <button
              key={action.key}
              type="button"
              onClick={action.onClick}
              disabled={action.disabled}
              aria-label={action.label}
              title={action.label}
              className={[
                action.active ? 'active' : '',
                action.danger ? 'danger' : '',
              ].filter(Boolean).join(' ') || undefined}
            >
              <action.Icon size={14} strokeWidth={2.5} aria-hidden="true" />
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
