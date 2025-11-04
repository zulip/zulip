import {allBrowsersRegex, baselineBrowserRegex} from "../generated/supported_browser_regex.ts";

export function is_browser_supported(): boolean {
    const user_agent = window.navigator.userAgent;

    // If the current user agent is from an esoteric browser that
    // browserlist does not cover, we should return true.
    if (!allBrowsersRegex.test(user_agent)) {
        return true;
    }

    return baselineBrowserRegex.test(user_agent);
}
