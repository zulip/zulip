import $ from "jquery";

import * as helpers from "./helpers";
import type {Prices} from "./helpers";
import {page_params} from "./page_params";

export const initialize = (): void => {
    $("#add-card-button").on("click", (e) => {
        const license_management = $<HTMLInputElement>(
            "input[type=radio][name=license_management]:checked",
        ).val()!;
        if (!helpers.is_valid_input($(`#${CSS.escape(license_management)}_license_count`))) {
            return;
        }
        e.preventDefault();

        helpers.create_ajax_request("/json/billing/upgrade", "autopay", [], "POST", (response) => {
            const response_data = helpers.stripe_session_url_schema.parse(response);
            window.location.replace(response_data.stripe_session_url);
        });
    });
    const prices: Prices = {
        annual: page_params.annual_price * (1 - page_params.percent_off / 100),
        monthly: page_params.monthly_price * (1 - page_params.percent_off / 100),
    };

    $<HTMLInputElement>("input[type=radio][name=schedule]").on("change", function () {
        helpers.update_charged_amount(prices, helpers.schedule_schema.parse(this.value));
    });

    $("#autopay_annual_price_per_month").text(
        `Pay annually ($${helpers.format_money(prices.annual / 12)}/user/month)`,
    );
    $("#autopay_monthly_price").text(
        `Pay monthly ($${helpers.format_money(prices.monthly)}/user/month)`,
    );
};

$(() => {
    initialize();
});
