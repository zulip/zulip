import * as common from "../common.ts";

export type UserOS = "android" | "ios" | "mac" | "windows" | "linux";

export function detect_user_os(): UserOS {
    if (/android/i.test(navigator.userAgent)) {
        return "android";
    }
    if (/iphone|ipad|ipod/i.test(navigator.userAgent)) {
        return "ios";
    }
    if (common.has_mac_keyboard()) {
        return "mac";
    }
    if (/win/i.test(navigator.userAgent)) {
        return "windows";
    }
    if (/linux/i.test(navigator.userAgent)) {
        return "linux";
    }
    return "mac"; // if unable to determine OS return Mac by default
}
