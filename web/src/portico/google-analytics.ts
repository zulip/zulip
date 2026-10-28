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
} else {
    config = () => {
        // No Google Analytics tracking configured.
    };
}
