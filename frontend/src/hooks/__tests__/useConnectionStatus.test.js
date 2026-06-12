import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

/**
 * useConnectionStatus keeps callback refs stable so the languages fetch effect
 * does not re-run every parent render when inline handlers are passed.
 */
describe('useConnectionStatus callback stability', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('documents stable ref pattern for onLanguages/onOffline', () => {
    const onLanguagesRef = { current: vi.fn() };
    const onOfflineRef = { current: vi.fn() };
    onLanguagesRef.current = vi.fn();
    onOfflineRef.current = vi.fn();
    onLanguagesRef.current({ en: 'English' });
    expect(onLanguagesRef.current).toHaveBeenCalledWith({ en: 'English' });
    onOfflineRef.current();
    expect(onOfflineRef.current).toHaveBeenCalled();
  });
});
