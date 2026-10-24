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
    // Analytics can't see it unless we send an event.
    $(document).on("change", ".top-menu-tab-input", function () {
        const menu_id = $(this)
            .attr("id")!
            .replace(/^top-menu-tab-/, "");
        gtag("event", "menu_open", {menu_id, layout: "wide"});
    });

    // The narrow-screen menu and its sections are <details> elements,
    // whose toggle event doesn't bubble, so we listen while it's
    // captured on the way down instead.
    document.addEventListener(
        "toggle",
        (event) => {
            const details = event.target;
            if (
                details instanceof HTMLDetailsElement &&
                details.open &&
                details.closest(".top-menu-mobile") !== null
            ) {
                gtag("event", "menu_open", {menu_id: details.dataset["menuId"], layout: "narrow"});
            }
        },
        {capture: true},
    );
} else {
    config = () => {
        // No Google Analytics tracking configured.
    };
}
