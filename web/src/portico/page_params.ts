import $ from "jquery";

export const page_params: {
    google_analytics_id: string | undefined;
} = $("#page-params").data("params");

if (!page_params) {
    throw new Error("Missing page-params");
}
