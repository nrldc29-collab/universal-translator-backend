import { MOBILE_BUILD_ID, isRemoteBuildNewer } from '../constants/mobileBuild';

describe('isRemoteBuildNewer', () => {
  test('detects newer fix number on same date', () => {
    expect(isRemoteBuildNewer('2026-06-09-fix60', '2026-06-09-fix59')).toBe(true);
    expect(isRemoteBuildNewer('2026-06-09-fix52', '2026-06-09-fix59')).toBe(false);
  });

  test('returns false for equal or missing ids', () => {
    expect(isRemoteBuildNewer(MOBILE_BUILD_ID, MOBILE_BUILD_ID)).toBe(false);
    expect(isRemoteBuildNewer('', MOBILE_BUILD_ID)).toBe(false);
    expect(isRemoteBuildNewer('2026-06-09-fix60', '')).toBe(false);
  });
});
