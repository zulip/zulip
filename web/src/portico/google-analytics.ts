import {gtag, install} from "ga-gtag";
import type {ConfigParams} from "ga-gtag";

import {page_params} from "../base_page_params.ts";

export let config: (info: ConfigParams) => void;

if (page_params.page_type !== "fallback" && page_params.google_analytics_id !== undefined) {
    const google_analytics_id = page_params.google_analytics_id;
    install(google_analytics_id);
    config = (info) => {
        gtag("config", google_analytics_id, info);
    };
} else {
    config = () => {
        // No Google Analytics tracking configured.
    };
}
