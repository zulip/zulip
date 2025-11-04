import {supportedBrowserRegex} from "../generated/supported_browser_regex.ts";

export function is_browser_supported(): boolean {
    return supportedBrowserRegex.test(window.navigator.userAgent);
}
