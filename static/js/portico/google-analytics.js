import {gtag, install} from "ga-gtag";

export let config;

if (page_params.google_analytics_id !== undefined) {
    install(page_params.google_analytics_id);
    config = (info) => gtag("config", page_params.google_analytics_id, info);
} else {
    config = () => {};
}
