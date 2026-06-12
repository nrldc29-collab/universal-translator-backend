import { getFriendlyPanelState, getFriendlyStatusLine } from '../utils/friendlyStatus';

describe('getFriendlyPanelState', () => {
  test('shows Connecting while network restored but socket not up yet', () => {
    expect(
      getFriendlyPanelState({
        isConnected: false,
        isConnecting: false,
        status: 'Network restored',
      }),
    ).toBe('Linking…');
  });

  test('maps stale network restored text to connect hint when offline', () => {
    expect(getFriendlyStatusLine('Network restored', { isConnected: false })).toBe('Link your bridge below');
    expect(getFriendlyStatusLine('Network restored', { isConnected: false, isConnecting: true })).toBe('Linking bridge…');
  });

  test('shows bridge ready when connected', () => {
    expect(
      getFriendlyPanelState({
        isConnected: true,
        isConnecting: false,
      }),
    ).toBe('Bridge ready');
  });

  test('shows Needs Wi-Fi when phone is on cellular with a LAN server URL', () => {
    expect(
      getFriendlyPanelState({
        isConnected: false,
        needsWifi: true,
        status: 'Network restored',
      }),
    ).toBe('Needs Wi‑Fi');
    expect(
      getFriendlyStatusLine('Network restored', { isConnected: false, needsWifi: true }),
    ).toBe('Join same Wi‑Fi as your PC');
  });
});
