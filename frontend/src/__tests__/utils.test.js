import { describe, it, expect } from 'vitest';
import {
  normalizeSessionId,
  fallbackSpeakerLabel,
  uniqueStrings,
  extractBrainPlan,
  compactRepairLabel,
  languageName,
  isFatalStreamError,
  speechRecognitionLanguage,
  detectLanguagePair,
  htTranslationHasGlossaryTerms,
  htToEnTranslationLooksValid,
  languagePairNeedsBackendStt,
  audioFileExtension,
  withAuthToken,
  summarizeLatencyHistory,
  base64ToArrayBuffer,
  buildTranslatePayload,
  readPersistedTargetLanguage,
  TARGET_LANGUAGE_OPTIONS,
} from '../utils';

// ---------- normalizeSessionId ----------

describe('normalizeSessionId', () => {
  it('strips special characters', () => {
    expect(normalizeSessionId('abc!@#def')).toBe('abcdef');
  });

  it('allows hyphens and underscores', () => {
    expect(normalizeSessionId('abc-def_123')).toBe('abc-def_123');
  });

  it('truncates to 64 chars', () => {
    const long = 'a'.repeat(80);
    expect(normalizeSessionId(long)).toHaveLength(64);
  });

  it('returns empty string for falsy input', () => {
    expect(normalizeSessionId(null)).toBe('');
    expect(normalizeSessionId(undefined)).toBe('');
    expect(normalizeSessionId('')).toBe('');
  });
});

// ---------- fallbackSpeakerLabel ----------

describe('fallbackSpeakerLabel', () => {
  it('returns Person for empty input', () => {
    expect(fallbackSpeakerLabel('')).toBe('Person');
    expect(fallbackSpeakerLabel(null)).toBe('Person');
    expect(fallbackSpeakerLabel('-')).toBe('Person');
  });

  it('extracts numeric suffix', () => {
    expect(fallbackSpeakerLabel('speaker1')).toBe('Person 1');
    expect(fallbackSpeakerLabel('A2')).toBe('Person 2');
  });

  it('strips speaker prefix', () => {
    expect(fallbackSpeakerLabel('speaker-A')).toBe('Person A');
    expect(fallbackSpeakerLabel('Speaker_B')).toBe('Person B');
  });

  it('returns raw value when no prefix match', () => {
    expect(fallbackSpeakerLabel('Doctor')).toBe('Doctor');
  });
});

// ---------- uniqueStrings ----------

describe('uniqueStrings', () => {
  it('removes duplicates case-insensitively', () => {
    expect(uniqueStrings(['Hello', 'hello', 'HELLO'])).toEqual(['Hello']);
  });

  it('trims whitespace before comparing', () => {
    expect(uniqueStrings(['  hi  ', 'hi'])).toEqual(['hi']);
  });

  it('filters out empty strings', () => {
    expect(uniqueStrings(['a', '', '  ', 'b'])).toEqual(['a', 'b']);
  });

  it('returns empty array for no input', () => {
    expect(uniqueStrings()).toEqual([]);
  });
});

// ---------- extractBrainPlan ----------

describe('extractBrainPlan', () => {
  it('extracts cip_response_plan', () => {
    const payload = { cip_response_plan: { strategy: 'direct' } };
    expect(extractBrainPlan(payload).plan).toEqual({ strategy: 'direct' });
  });

  it('falls back to response_plan', () => {
    const payload = { response_plan: { strategy: 'guarded' } };
    expect(extractBrainPlan(payload).plan).toEqual({ strategy: 'guarded' });
  });

  it('extracts hints from cip_client_hints', () => {
    const payload = { cip_client_hints: { skip_tts: true } };
    expect(extractBrainPlan(payload).hints).toEqual({ skip_tts: true });
  });

  it('extracts repair options', () => {
    const opts = [{ type: 'repeat_terms' }];
    const payload = { cip_repair_options: opts };
    expect(extractBrainPlan(payload).repairOptions).toEqual(opts);
  });

  it('returns safe defaults for empty payload', () => {
    const result = extractBrainPlan({});
    expect(result.plan).toBeNull();
    expect(result.hints).toEqual({});
    expect(result.repairOptions).toEqual([]);
  });
});

// ---------- compactRepairLabel ----------

describe('compactRepairLabel', () => {
  it('returns Using XX for auto_switch_source_language', () => {
    expect(compactRepairLabel({ type: 'auto_switch_source_language', language: 'es' })).toBe('Using ES');
  });

  it('returns Switch to XX for switch_source_language', () => {
    expect(compactRepairLabel({ type: 'switch_source_language', language: 'fr' })).toBe('Switch to FR');
  });

  it('returns label strings for known types', () => {
    expect(compactRepairLabel({ type: 'repeat_terms' })).toBe('Repeat exact terms');
    expect(compactRepairLabel({ type: 'confirm_exact' })).toBe('Confirm exact words');
    expect(compactRepairLabel({ type: 'repeat_slowly' })).toBe('Repeat slowly');
    expect(compactRepairLabel({ type: 'preserve_code_switch' })).toBe('Keep mixed language');
  });

  it('returns option.label as fallback', () => {
    expect(compactRepairLabel({ type: 'unknown', label: 'Try again' })).toBe('Try again');
  });

  it('returns Repair as last resort', () => {
    expect(compactRepairLabel({})).toBe('Repair');
  });
});

// ---------- languageName ----------

describe('languageName', () => {
  it('looks up from TARGET_LANGUAGE_OPTIONS', () => {
    expect(languageName('en')).toBe('English');
    expect(languageName('es')).toBe('Spanish');
    expect(languageName('ht')).toBe('Haitian Creole');
  });

  it('prefers the languages map over built-in options', () => {
    expect(languageName('en', { en: 'British English' })).toBe('British English');
  });

  it('uppercases unknown codes', () => {
    expect(languageName('jp')).toBe('JP');
  });

  it('returns empty string for falsy code', () => {
    expect(languageName('')).toBe('');
    expect(languageName(null)).toBe('');
  });
});

// ---------- isFatalStreamError ----------

describe('isFatalStreamError', () => {
  it('matches quota errors', () => {
    expect(isFatalStreamError('quota exceeded')).toBe(true);
  });

  it('matches auth errors', () => {
    expect(isFatalStreamError('not authorized')).toBe(true);
    expect(isFatalStreamError('Unauthorized')).toBe(true);
    expect(isFatalStreamError('Forbidden')).toBe(true);
  });

  it('matches buffer limit', () => {
    expect(isFatalStreamError('buffer limit reached')).toBe(true);
  });

  it('matches warming messages', () => {
    expect(isFatalStreamError('Models still loading. Wait for LIVE.')).toBe(true);
  });

  it('returns false for non-fatal messages', () => {
    expect(isFatalStreamError('connection closed')).toBe(false);
    expect(isFatalStreamError('')).toBe(false);
  });
});

// ---------- speechRecognitionLanguage ----------

describe('speechRecognitionLanguage', () => {
  it('maps known codes to locale strings', () => {
    expect(speechRecognitionLanguage('en')).toBe('en-US');
    expect(speechRecognitionLanguage('es')).toBe('es-ES');
    expect(speechRecognitionLanguage('ht')).toBe('ht-HT');
    expect(speechRecognitionLanguage('fr')).toBe('fr-FR');
    expect(speechRecognitionLanguage('pt')).toBe('pt-BR');
  });

  it('normalizes codes with region suffix', () => {
    expect(speechRecognitionLanguage('en-GB')).toBe('en-US');
  });

  it('returns the code itself for unknown languages', () => {
    expect(speechRecognitionLanguage('xx')).toBe('xx');
  });

  it('defaults to en-US for falsy input', () => {
    expect(speechRecognitionLanguage('')).toBe('en-US');
    expect(speechRecognitionLanguage(null)).toBe('en-US');
  });
});

describe('detectLanguagePair', () => {
  it('detects Haitian Creole in an EN↔HT pair', () => {
    expect(detectLanguagePair('mwen bezwen èd', 'en', 'ht', 'en')).toBe('ht');
  });

  it('detects English in an EN↔HT pair', () => {
    expect(detectLanguagePair('I need help today', 'en', 'ht', 'ht')).toBe('en');
  });

  it('keeps last language on ambiguous short text', () => {
    expect(detectLanguagePair('ok', 'en', 'ht', 'ht')).toBe('ht');
  });
});

// ---------- languagePairNeedsBackendStt ----------

describe('languagePairNeedsBackendStt', () => {
  it('returns true when Haitian Creole is in the pair', () => {
    expect(languagePairNeedsBackendStt('en', 'ht')).toBe(true);
    expect(languagePairNeedsBackendStt('ht', 'en')).toBe(true);
  });

  it('returns false for non-HT pairs', () => {
    expect(languagePairNeedsBackendStt('en', 'es')).toBe(false);
  });
});

// ---------- htToEnTranslationLooksValid ----------

describe('htToEnTranslationLooksValid', () => {
  it('accepts help/need translations', () => {
    expect(htToEnTranslationLooksValid('I need help')).toBe(true);
  });

  it('rejects unrelated text', () => {
    expect(htToEnTranslationLooksValid('Bonjou')).toBe(false);
  });
});

// ---------- htTranslationHasGlossaryTerms ----------

describe('htTranslationHasGlossaryTerms', () => {
  it('matches Creole glossary output', () => {
    expect(htTranslationHasGlossaryTerms('Mwen bezwen èd')).toBe(true);
    expect(htTranslationHasGlossaryTerms('Mwen bezwen ed')).toBe(true);
  });

  it('rejects unrelated text', () => {
    expect(htTranslationHasGlossaryTerms('Bonjou')).toBe(false);
  });

  it('does not treat string indices as glossary hits', () => {
    expect(htTranslationHasGlossaryTerms('abc')).toBe(false);
  });
});

// ---------- audioFileExtension ----------

describe('audioFileExtension', () => {
  it('returns .m4a for mp4/aac', () => {
    expect(audioFileExtension('audio/mp4')).toBe('.m4a');
    expect(audioFileExtension('audio/aac')).toBe('.m4a');
  });

  it('returns .ogg for ogg', () => {
    expect(audioFileExtension('audio/ogg')).toBe('.ogg');
  });

  it('returns .webm as default', () => {
    expect(audioFileExtension('audio/webm')).toBe('.webm');
    expect(audioFileExtension('unknown')).toBe('.webm');
  });
});

// ---------- withAuthToken ----------

describe('withAuthToken', () => {
  it('appends token as query param', () => {
    expect(withAuthToken('http://host/ws', 'tok123')).toBe('http://host/ws?access_token=tok123');
  });

  it('uses & when URL already has params', () => {
    expect(withAuthToken('http://host/ws?foo=1', 'tok')).toBe('http://host/ws?foo=1&access_token=tok');
  });

  it('returns URL unchanged when no token', () => {
    expect(withAuthToken('http://host/ws', '')).toBe('http://host/ws');
    expect(withAuthToken('http://host/ws', null)).toBe('http://host/ws');
  });
});

// ---------- summarizeLatencyHistory ----------

describe('summarizeLatencyHistory', () => {
  it('returns nulls for empty history', () => {
    expect(summarizeLatencyHistory([])).toEqual({ average: null, best: null });
  });

  it('returns nulls when no finite totals', () => {
    expect(summarizeLatencyHistory([{ total: null }, { total: -1 }])).toEqual({ average: null, best: null });
  });

  it('calculates average and best', () => {
    const history = [{ total: 100 }, { total: 200 }, { total: 300 }];
    expect(summarizeLatencyHistory(history)).toEqual({ average: 200, best: 100 });
  });
});

// ---------- base64ToArrayBuffer ----------

describe('base64ToArrayBuffer', () => {
  it('decodes a base64 string to ArrayBuffer', () => {
    const original = new Uint8Array([72, 101, 108, 108, 111]); // "Hello"
    const base64 = btoa(String.fromCharCode(...original));
    const result = base64ToArrayBuffer(base64);
    expect(result).toBeInstanceOf(ArrayBuffer);
    expect(new Uint8Array(result)).toEqual(original);
  });

  it('produces correct byte length', () => {
    const bytes = new Uint8Array(100).fill(0xff);
    const base64 = btoa(String.fromCharCode(...bytes));
    expect(base64ToArrayBuffer(base64).byteLength).toBe(100);
  });

  it('round-trips audio-like binary data', () => {
    const wav = new Uint8Array([82, 73, 70, 70]); // "RIFF"
    const base64 = btoa(String.fromCharCode(...wav));
    const buf = base64ToArrayBuffer(base64);
    expect(String.fromCharCode(...new Uint8Array(buf))).toBe('RIFF');
  });
});

// ---------- buildTranslatePayload ----------

describe('buildTranslatePayload', () => {
  const base = {
    text: 'Hello',
    sourceLanguage: 'en',
    targetLanguage: 'es',
    sessionId: 'sess-1',
    deviceId: 'dev-abc',
    speakerName: 'Speaker A',
    speakerMode: 'auto',
  };

  it('maps camelCase props to snake_case keys', () => {
    const body = buildTranslatePayload(base);
    expect(body.source_language).toBe('en');
    expect(body.target_language).toBe('es');
    expect(body.session_id).toBe('sess-1');
    expect(body.device_id).toBe('dev-abc');
    expect(body.speaker_name).toBe('Speaker A');
    expect(body.speaker_mode).toBe('auto');
    expect(body.text).toBe('Hello');
  });

  it('defaults synthesize_audio to false', () => {
    expect(buildTranslatePayload(base).synthesize_audio).toBe(false);
  });

  it('sets synthesize_audio to true when requested', () => {
    expect(buildTranslatePayload({ ...base, synthesizeAudio: true }).synthesize_audio).toBe(true);
  });

  it('omits audio_response_format when not set', () => {
    expect('audio_response_format' in buildTranslatePayload(base)).toBe(false);
  });

  it('includes audio_response_format when provided', () => {
    const body = buildTranslatePayload({ ...base, audioResponseFormat: 'url' });
    expect(body.audio_response_format).toBe('url');
  });

  it('produces a plain serialisable object', () => {
    expect(() => JSON.stringify(buildTranslatePayload(base))).not.toThrow();
  });
});

// ---------- readPersistedTargetLanguage ----------

describe('readPersistedTargetLanguage', () => {
  it('defaults to Haitian Creole for EN↔HT first-run users', () => {
    expect(readPersistedTargetLanguage()).toBe('ht');
  });
});

// ---------- TARGET_LANGUAGE_OPTIONS sanity ----------

describe('TARGET_LANGUAGE_OPTIONS', () => {
  it('contains en, es, ht entries', () => {
    const codes = TARGET_LANGUAGE_OPTIONS.map((o) => o.code);
    expect(codes).toContain('en');
    expect(codes).toContain('es');
    expect(codes).toContain('ht');
  });
});
