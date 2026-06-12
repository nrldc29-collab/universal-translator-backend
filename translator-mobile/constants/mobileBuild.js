export const MOBILE_BUILD_ID = "2026-06-11-fix152";

/** True when Metro/server build is ahead of the JS bundle on the phone (safe to reload). */
export function isRemoteBuildNewer(remoteId, localId = MOBILE_BUILD_ID) {
  const remote = String(remoteId || "").trim();
  const local = String(localId || "").trim();
  if (!remote || !local || remote === local) return false;
  const remoteFix = remote.match(/fix(\d+)$/i);
  const localFix = local.match(/fix(\d+)$/i);
  if (remoteFix && localFix) {
    return Number(remoteFix[1]) > Number(localFix[1]);
  }
  return remote > local;
}
