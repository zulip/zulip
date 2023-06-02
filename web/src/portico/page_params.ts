import $ from "jquery";

import type {Contributor} from "./team";

export const page_params: {
    contributors: Contributor[] | undefined;
    google_analytics_id: string | undefined;
} = $("#page-params").data("params");

if (!page_params) {
    throw new Error("Missing page-params");
}
