import $ from "jquery";

import * as blueslip from "../blueslip";
import * as common from "../common";

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

export function activate_correct_tab($tabbed_section: JQuery): void {
    const user_os = detect_user_os();
    const desktop_os = new Set(["mac", "linux", "windows"]);
    const $li = $tabbed_section.find("ul.nav li");
    const $blocks = $tabbed_section.find(".blocks div");

    $li.each(function () {
        const tab_key = this.dataset.tabKey;
        $(this).removeClass("active");
        if (tab_key === user_os) {
            $(this).addClass("active");
        }

        if (desktop_os.has(user_os) && tab_key === "desktop-web") {
            $(this).addClass("active");
        }
    });

    $blocks.each(function () {
        const tab_key = this.dataset.tabKey;
        $(this).removeClass("active");
        if (tab_key === user_os) {
            $(this).addClass("active");
        }

        if (desktop_os.has(user_os) && tab_key === "desktop-web") {
            $(this).addClass("active");
        }
    });

    // if no tab was activated, just activate the first one
    const $active_list_items = $li.filter(".active");
    if (!$active_list_items.length) {
        $li.first().addClass("active");
        const tab_key = $li.first()[0].dataset.tabKey;
        if (tab_key) {
            $blocks.filter("[data-tab-key=" + tab_key + "]").addClass("active");
        } else {
            blueslip.error("Tabbed instructions widget has no tabs to activate!");
        }
    }
}

$(".tabbed-section").each(function () {
    activate_correct_tab($(this));
});
