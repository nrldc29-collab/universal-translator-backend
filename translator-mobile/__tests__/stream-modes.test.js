import { describeLiveMode, formatPeerTurn, summarizeRepair } from '../services/stream-modes';

describe('describeLiveMode', () => {
  test('describes the best streaming mode as healthy', () => {
    const m = describeLiveMode({ type: 'mode', mode: 'streaming_stt', recommend_fallback: false });
    expect(m.mode).toBe('streaming_stt');
    expect(m.degraded).toBe(false);
    expect(m.label).toBe('Live streaming');
  });

  test('flags degraded when fallback is recommended', () => {
    const m = describeLiveMode({ type: 'mode', mode: 'degraded', recommend_fallback: true, reason: 'down' });
    expect(m.degraded).toBe(true);
    expect(m.recommendFallback).toBe(true);
    expect(m.hint).toBe('down');
  });

  test('handles missing fields gracefully', () => {
    const m = describeLiveMode();
    expect(m.mode).toBe('unknown');
    expect(m.label).toBe('Connecting');
    expect(m.degraded).toBe(false);
  });
});

describe('formatPeerTurn', () => {
  test('formats a peer translation with the speaker label', () => {
    expect(formatPeerTurn({ speaker_label: 'Person 2', translated_text: 'hola mundo' })).toBe('Person 2: hola mundo');
  });

  test('returns empty string when there is no translation', () => {
    expect(formatPeerTurn({ speaker_label: 'Person 2', translated_text: '   ' })).toBe('');
  });

  test('falls back to a generic speaker name', () => {
    expect(formatPeerTurn({ translated_text: 'hi' })).toBe('Speaker: hi');
  });
});

describe('summarizeRepair', () => {
  test('joins option labels', () => {
    const summary = summarizeRepair({ options: [{ label: 'Repeat slowly' }, { label: "Meaning of 'bank'" }] });
    expect(summary).toBe("Repeat slowly \u00b7 Meaning of 'bank'");
  });

  test('returns empty string with no options', () => {
    expect(summarizeRepair({})).toBe('');
  });
});
