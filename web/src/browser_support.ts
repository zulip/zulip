import {allBrowsersRegex, baselineBrowserRegex} from "../generated/supported_browser_regex.ts";

export function is_browser_unsupported_old_version(): boolean {
    const user_agent = window.navigator.userAgent;

    // In order to avoid showing warnings for esoteric browsers or
    // desktop apps like Rambox or Ferdium, we only consider browsers
    // that BrowsersList tracks.
    if (!allBrowsersRegex.test(user_agent)) {
        return false;
    }

    return !baselineBrowserRegex.test(user_agent);
}
