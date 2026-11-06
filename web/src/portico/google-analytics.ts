import {gtag, install} from "ga-gtag";
import type {ConfigParams} from "ga-gtag";
import {$} from "jquery";

import {page_params} from "../base_page_params.ts";

export let config: (info: ConfigParams) => void;

if (page_params.google_analytics_id !== undefined) {
    install(page_params.google_analytics_id);
    config = (info) => {
        gtag("config", page_params.google_analytics_id!, info);
    };

    // Google Analytics doesn't record clicks on links within our site,
    // so we send our own event to tell apart links like several
    // "Get started" buttons that all go to /.
    $(document).on("click", ".analytics-click", function () {
        gtag("event", "marketing_click", {button_id: $(this).attr("data-button-id")!});
    });

    // Opening a navigation menu doesn't load a page, so Google
    // Analytics can't see it unless we send an event. The same menus
    // open as dropdowns on wide screens and as sections of the
    // narrow-screen menu; the width matches the breakpoint in
    // navbar.css.
    const narrow_layout = window.matchMedia("(width <= 1100px)");
    $(document).on("change", ".top-menu-tab-input", function () {
        const menu_id = $(this)
            .attr("id")!
            .replace(/^top-menu-tab-/, "");
        gtag("event", "menu_open", {menu_id, layout: narrow_layout.matches ? "narrow" : "wide"});
    });

    $(document).on("change", "#top-menu-mobile-toggle", function () {
        if ($(this).prop("checked")) {
            gtag("event", "menu_open", {menu_id: "menu", layout: "narrow"});
        }
    });
} else {
    config = () => {
        // No Google Analytics tracking configured.
    };
}
