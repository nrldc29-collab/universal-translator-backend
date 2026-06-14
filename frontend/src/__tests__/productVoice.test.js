import { describe, expect, it } from 'vitest';

import { micInteractionAllowed, micLabels } from '../utils/productVoice';

describe('micInteractionAllowed', () => {
  it('allows tap while bridge is warming or checking', () => {
    expect(micInteractionAllowed({ connectionStatus: 'warming', micPermission: 'available' })).toBe(true);
    expect(micInteractionAllowed({ connectionStatus: 'checking', micPermission: 'available' })).toBe(true);
    expect(micInteractionAllowed({ connectionStatus: 'online', micPermission: 'available' })).toBe(true);
  });

  it('blocks only offline bridge or blocked mic permission', () => {
    expect(micInteractionAllowed({ connectionStatus: 'offline', micPermission: 'available' })).toBe(false);
    expect(micInteractionAllowed({ connectionStatus: 'online', micPermission: 'denied' })).toBe(false);
    expect(micInteractionAllowed({ connectionStatus: 'online', micPermission: 'unavailable' })).toBe(false);
  });
});

describe('micLabels', () => {
  it('shows warming copy without treating the mic as unavailable', () => {
    expect(
      micLabels({
        connectionStatus: 'warming',
        micReady: true,
        playing: false,
        perceivedListening: false,
        processing: false,
      }),
    ).toBe('Opening bridge…');
  });
});
