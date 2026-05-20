/**
 * LanguageDock — source/target language pickers + quick action row.
 *
 * Extracted from `main.jsx` so the App component renders less inline JSX.
 * All state still lives in App; this component is purely presentational
 * apart from the `setTargetLanguage(code)` callback fired by the radio
 * buttons.
 *
 * Quick actions are passed in as a `quickActions` array so the parent
 * controls which actions are available, their labels, icons, and
 * onClick handlers.
 */

import React from 'react';
import { ArrowLeftRight, Check } from 'lucide-react';

import { TARGET_LANGUAGE_OPTIONS } from '../utils';

export default function LanguageDock({
  sourceLanguageLabel,
  targetLanguageLabel,
  targetLanguage,
  setTargetLanguage,
  recording,
  processing,
  brainUi = {},
  quickActions = [],
}) {
  return (
    <section className="language-dock" aria-label="Target language">
      <div className="language-direction" aria-hidden="true">
        <span className="route-pill">
          <small>From</small>
          <strong>{sourceLanguageLabel}</strong>
        </span>
        <span className="route-switch">
          <ArrowLeftRight size={15} strokeWidth={2.4} />
        </span>
        <span className="route-pill target">
          <small>To</small>
          <strong>{targetLanguageLabel}</strong>
        </span>
      </div>
      {brainUi.hints?.language_auto_repaired && (
        <div className="language-repair-line" role="status">
          <Check size={14} strokeWidth={2.6} />
          <span>{brainUi.message || `Source set to ${sourceLanguageLabel}`}</span>
        </div>
      )}
      <div className="language-options" role="radiogroup" aria-label="Target language">
        {TARGET_LANGUAGE_OPTIONS.map((opt) => {
          const active = targetLanguage === opt.code;
          return (
            <button
              key={opt.code}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setTargetLanguage(opt.code)}
              disabled={recording || processing}
              className={active ? 'active' : ''}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      <div className="quick-actions" aria-label="Quick interpreter actions">
        {quickActions.map((action) => (
          <button
            key={action.key}
            type="button"
            onClick={action.onClick}
            disabled={action.disabled}
            aria-label={action.label}
            title={action.label}
          >
            <action.Icon size={14} strokeWidth={2.5} aria-hidden="true" />
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
