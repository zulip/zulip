import * as common from "../common.ts";

export type UserOS = "android" | "ios" | "mac" | "windows" | "linux";

export function detect_user_os(): UserOS {
    if (/android/i.test(navigator.userAgent)) {
        return "android";
    }
    if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
        return "ios";
    }
    // Prioritize Linux detection
    if (/linux/i.test(navigator.userAgent)) {
        return "linux";
    }
    if (/win/i.test(navigator.userAgent)) {
        return "windows";
    }
    if (common.has_mac_keyboard()) {
        return "mac";
    }
    return "mac"; // if unable to determine OS return Mac by default
}
