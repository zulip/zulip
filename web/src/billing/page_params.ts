import $ from "jquery";

// Don't remove page_params here yet, since we still use them later.
// For example, "#page_params" is used again through `sentry.ts`, which
// imports the main `src/page_params` module.
export const page_params: {
    annual_price: number;
    monthly_price: number;
    percent_off: number;
    seat_count: number;
} = $("#page-params").data("params");

if (!page_params) {
    throw new Error("Missing page-params");
}
