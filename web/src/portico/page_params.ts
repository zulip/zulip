import $ from "jquery";

export const page_params = $("#page-params").data("params");

if (!page_params) {
    throw new Error("Missing page-params");
}
