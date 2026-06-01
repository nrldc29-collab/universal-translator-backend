/**
 * LanguageDock -- language pair display with grouped dropdowns for both languages.
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ArrowLeftRight, ChevronDown, Check, Search } from 'lucide-react';
import { TARGET_LANGUAGE_OPTIONS } from '../utils';

const GROUPS = [
  { label: 'Popular',  codes: ['en','es','fr','pt','ht'] },
  { label: 'European', codes: ['de','it','nl','ru'] },
  { label: 'Asian',    codes: ['zh','ja','ko','hi'] },
  { label: 'Other',    codes: ['ar'] },
];

function buildGrouped() {
  const byCode = Object.fromEntries(TARGET_LANGUAGE_OPTIONS.map(o => [o.code, o]));
  return GROUPS.map(g => ({ ...g, options: g.codes.map(c => byCode[c]).filter(Boolean) })).filter(g => g.options.length);
}

function LangDropdown({ value, onChange, disabled, variant = 'target' }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef(null);
  const searchRef = useRef(null);
  const allGroups = buildGrouped();
  const current = TARGET_LANGUAGE_OPTIONS.find(o => o.code === value);

  const groups = query.trim()
    ? [{ label: 'Results', options: TARGET_LANGUAGE_OPTIONS.filter(o =>
        o.label.toLowerCase().includes(query.toLowerCase()) ||
        (o.native && o.native.toLowerCase().includes(query.toLowerCase())) ||
        o.code.toLowerCase().includes(query.toLowerCase())
      ) }]
    : allGroups;

  useEffect(() => {
    if (!open) { setQuery(''); return; }
    setTimeout(() => searchRef.current?.focus(), 40);
    const handleClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const handleKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const isTarget = variant === 'target';

  return (
    <div ref={ref} className="lang-dropdown-wrap">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`lang-dropdown-trigger ${isTarget ? 'target' : 'source'} ${open ? 'open' : ''}`}
      >
        <span className="lang-dropdown-flag">{current?.flag || '🌐'}</span>
        <span className={`lang-dropdown-label ${isTarget ? 'target' : ''}`}>
          {current?.label || value}
        </span>
        <ChevronDown
          size={13}
          strokeWidth={2.2}
          className={`lang-dropdown-chevron ${open ? 'open' : ''}`}
        />
      </button>

      {open && (
        <div className="lang-dropdown-menu" role="listbox">
          {/* Search */}
          <div className="lang-search-row">
            <Search size={12} strokeWidth={2.5} className="lang-search-icon" />
            <input
              ref={searchRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search language…"
              className="lang-search-input"
            />
            {query && (
              <button type="button" className="lang-search-clear" onClick={() => setQuery('')}>
                ×
              </button>
            )}
          </div>
          <div className="lang-dropdown-list">
            {groups.map((g, gi) => (
              <div key={g.label}>
                <div className={`lang-group-label ${gi > 0 ? 'bordered' : ''}`}>{g.label}</div>
                {g.options.map(opt => {
                  const sel = opt.code === value;
                  return (
                    <button
                      key={opt.code}
                      type="button"
                      role="option"
                      aria-selected={sel}
                      onClick={() => { onChange(opt.code); setOpen(false); }}
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
            ))}
          </div>
        </div>
      )}
    </div>
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
  brainUi = {},
  quickActions = [],
}) {
  const disabled = recording || processing;
  const [flipped, setFlipped] = useState(false);

  return (
    <section className="language-dock" aria-label="Language settings">
      <div className="lang-dock-row">
        {/* Source language */}
        {setSourceLanguage ? (
          <LangDropdown
            value={sourceLanguage}
            onChange={setSourceLanguage}
            disabled={disabled}
            variant="source"
          />
        ) : (
          <div className="lang-static-chip">
            <span className="lang-static-label">{sourceLanguageLabel}</span>
          </div>
        )}

        {/* Swap button */}
        <button
          type="button"
          disabled={disabled}
          aria-label="Swap languages"
          className="lang-swap-btn"
          onClick={() => {
            if (disabled) return;
            setFlipped(f => !f);
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

        {/* Target language */}
        <LangDropdown
          value={targetLanguage}
          onChange={setTargetLanguage}
          disabled={disabled}
          variant="target"
        />
      </div>

      {/* Quick actions */}
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
                action.active  ? 'active'  : '',
                action.danger  ? 'danger'  : '',
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
