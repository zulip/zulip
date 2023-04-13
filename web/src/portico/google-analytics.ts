import {gtag, install} from "ga-gtag";

import {page_params} from "../page_params";

type Info = {
    page_path: string;
};

export let config: (info: Info) => void;

if (page_params.google_analytics_id !== undefined) {
    install(page_params.google_analytics_id);
    config = (info) => gtag("config", page_params.google_analytics_id, info);
} else {
    config = () => undefined;
}
