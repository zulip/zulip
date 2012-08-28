import {gtag, install} from "ga-gtag";
import type {ConfigParams} from "ga-gtag";

import {page_params} from "../base_page_params.ts";

export let config: (info: ConfigParams) => void;

if (page_params.google_analytics_id !== undefined) {
    install(page_params.google_analytics_id);
    config = (info) => {
        gtag("config", page_params.google_analytics_id!, info);
    };
} else {
    config = () => {
        // No Google Analytics tracking configured.
    };
}
