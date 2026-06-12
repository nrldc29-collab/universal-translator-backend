import {
  isLocalLanServerUrl,
  isNetworkTypeKnown,
  isPhoneOnWifi,
  needsWifiForLanServer,
} from '../utils/serverUrl';

describe('isLocalLanServerUrl', () => {
  test('detects private LAN hosts', () => {
    expect(isLocalLanServerUrl('http://192.168.12.243:8000')).toBe(true);
    expect(isLocalLanServerUrl('http://10.0.0.4:8000')).toBe(true);
  });

  test('rejects localhost', () => {
    expect(isLocalLanServerUrl('http://localhost:8000')).toBe(false);
    expect(isLocalLanServerUrl('http://127.0.0.1:8000')).toBe(false);
  });

  test('detects cellular vs wifi for LAN servers', () => {
    const lan = 'http://192.168.12.243:8000';
    expect(isPhoneOnWifi({ type: 'WIFI' })).toBe(true);
    expect(isPhoneOnWifi({ type: 'ETHERNET' })).toBe(true);
    expect(isPhoneOnWifi({ type: 'CELLULAR' })).toBe(false);
    expect(needsWifiForLanServer({ type: 'CELLULAR' }, lan)).toBe(true);
    expect(needsWifiForLanServer({ type: 'MOBILE' }, lan)).toBe(true);
    expect(needsWifiForLanServer({ type: 'WIFI' }, lan)).toBe(false);
    expect(needsWifiForLanServer({ type: 'UNKNOWN' }, lan)).toBe(false);
    expect(needsWifiForLanServer(null, lan)).toBe(false);
  });

  test('does not block LAN when VPN is active on Wi-Fi', () => {
    const lan = 'http://192.168.12.243:8000';
    expect(needsWifiForLanServer({ type: 'VPN', isConnected: true }, lan)).toBe(false);
  });

  test('isNetworkTypeKnown rejects unknown network types', () => {
    expect(isNetworkTypeKnown({ type: 'WIFI' })).toBe(true);
    expect(isNetworkTypeKnown({ type: 'CELLULAR' })).toBe(true);
    expect(isNetworkTypeKnown({ type: 'UNKNOWN' })).toBe(false);
    expect(isNetworkTypeKnown({ type: '' })).toBe(false);
    expect(isNetworkTypeKnown(null)).toBe(false);
  });

  test('treats public tunnel hosts as non-LAN', () => {
    const tunnel = 'https://anai.example.trycloudflare.com';
    expect(isLocalLanServerUrl(tunnel)).toBe(false);
    expect(needsWifiForLanServer({ type: 'CELLULAR' }, tunnel)).toBe(false);
  });
});
