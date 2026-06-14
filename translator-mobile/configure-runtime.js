/** Side-effect import: quiet Expo console before App and hooks load. */
import { configureMobileRuntime } from "./utils/mobileLogger";

configureMobileRuntime();
