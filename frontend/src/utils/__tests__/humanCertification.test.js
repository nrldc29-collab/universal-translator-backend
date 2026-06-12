import { describe, expect, it } from 'vitest';
import {
  humanCertStep,
  shouldBlockTtsForCert,
  resolveConfidenceWarning,
} from '../humanCertification';

describe('humanCertification', () => {
  it('maps required step from payload', () => {
    expect(humanCertStep({ human_certification_step: 'required' })).toBe('required');
    expect(shouldBlockTtsForCert('required')).toBe(true);
  });

  it('falls back to advisory for native listen', () => {
    expect(humanCertStep({ native_speaker_listen_recommended: true })).toBe('advisory');
    expect(shouldBlockTtsForCert('advisory')).toBe(false);
  });

  it('builds warning copy for high-stakes payloads', () => {
    const message = resolveConfidenceWarning({ needs_confirmation: true });
    expect(message).toContain('High-stakes');
  });
});
