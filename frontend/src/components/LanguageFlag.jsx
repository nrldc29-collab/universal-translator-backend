/**
 * LanguageFlag -- Displays language code with flag emoji and full name
 * Includes smooth animations and accessibility support
 */

import React from 'react';

// Language to flag emoji mapping
const LANGUAGE_FLAGS = {
  en: '🇺🇸',
  es: '🇪🇸',
  fr: '🇫🇷',
  de: '🇩🇪',
  it: '🇮🇹',
  pt: '🇵🇹',
  nl: '🇳🇱',
  ru: '🇷🇺',
  zh: '🇨🇳',
  ja: '🇯🇵',
  ko: '🇰🇷',
  ar: '🇸🇦',
  hi: '🇮🇳',
  ht: '🇭🇹',
  // Additional mappings
  'en-US': '🇺🇸',
  'en-GB': '🇬🇧',
  'es-MX': '🇲🇽',
  'es-ES': '🇪🇸',
  'pt-BR': '🇧🇷',
  'zh-CN': '🇨🇳',
  'zh-TW': '🇹🇼',
  'ar-SA': '🇸🇦',
};

// Language names
const LANGUAGE_NAMES = {
  en: 'English',
  es: 'Spanish',
  fr: 'French',
  de: 'German',
  it: 'Italian',
  pt: 'Portuguese',
  nl: 'Dutch',
  ru: 'Russian',
  zh: 'Chinese',
  ja: 'Japanese',
  ko: 'Korean',
  ar: 'Arabic',
  hi: 'Hindi',
  ht: 'Haitian Creole',
};

export default function LanguageFlag({
  languageCode = '',
  showFullName = false,
  showFlag = true,
  size = 'medium',
  isActive = false,
  isSource = false,
  isTarget = false,
  className = '',
}) {
  const normalizedCode = languageCode?.toLowerCase().split('-')[0] || '';
  const flag = showFlag ? (LANGUAGE_FLAGS[languageCode] || LANGUAGE_FLAGS[normalizedCode] || '🌐') : null;
  const name = LANGUAGE_NAMES[normalizedCode] || languageCode?.toUpperCase() || 'Unknown';

  const sizeClasses = {
    small: 'lang-flag-sm',
    medium: 'lang-flag-md',
    large: 'lang-flag-lg',
  };

  const getRole = () => {
    if (isSource) return ' (source)';
    if (isTarget) return ' (target)';
    return '';
  };

  return (
    <span
      className={`language-flag ${sizeClasses[size]} ${isActive ? 'active' : ''} ${className}`}
      role="img"
      aria-label={`${name}${getRole()}`}
      title={`${name}${getRole()}`}
    >
      {flag && (
        <span 
          className="flag-emoji" 
          aria-hidden="true"
        >
          {flag}
        </span>
      )}
      <span className="language-code">{languageCode?.toUpperCase() || '--'}</span>
      {showFullName && (
        <span className="language-name">{name}</span>
      )}
      {(isSource || isTarget) && (
        <span className="language-role" aria-hidden="true">
          {isSource ? '→' : '←'}
        </span>
      )}
    </span>
  );
}

// Utility function to get language info
export function getLanguageInfo(code) {
  const normalized = code?.toLowerCase().split('-')[0] || '';
  return {
    code: normalized,
    flag: LANGUAGE_FLAGS[code] || LANGUAGE_FLAGS[normalized] || '🌐',
    name: LANGUAGE_NAMES[normalized] || code?.toUpperCase() || 'Unknown',
  };
}
