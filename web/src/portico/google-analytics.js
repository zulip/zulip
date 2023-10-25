import {gtag, install} from "ga-gtag";
import $ from "jquery";

export let config;
const google_analytics_id = $("#page-params").data("params").google_analytics_id;

if (google_analytics_id !== undefined) {
    install(google_analytics_id);
    config = (info) => gtag("config", google_analytics_id, info);
} else {
    config = () => {};
}
