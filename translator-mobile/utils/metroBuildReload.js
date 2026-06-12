import * as SecureStore from "expo-secure-store";
import { MOBILE_BUILD_ID, isRemoteBuildNewer } from "../constants/mobileBuild";

const RELOAD_PREFIX = "anai_metro_reload_";

/** One auto-reload per Metro build id (avoids infinite reload when Expo cache is stuck). */
export async function shouldAutoReloadForMetro(remoteBuildId, localBuildId = MOBILE_BUILD_ID) {
  const remote = String(remoteBuildId || "").trim();
  if (!isRemoteBuildNewer(remote, localBuildId)) return false;
  const key = `${RELOAD_PREFIX}${remote}`;
  try {
    if (await SecureStore.getItemAsync(key)) return false;
    await SecureStore.setItemAsync(key, "1");
    return true;
  } catch {
    return false;
  }
}
