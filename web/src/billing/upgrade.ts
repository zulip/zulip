import $ from "jquery";

import * as helpers from "./helpers";
import type {Prices} from "./helpers";
import {page_params} from "./page_params";

export const initialize = (): void => {
    helpers.set_tab("upgrade");
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

    $("#invoice-button").on("click", (e) => {
        if (!helpers.is_valid_input($("#invoiced_licenses"))) {
            return;
        }
        e.preventDefault();
        helpers.create_ajax_request("/json/billing/upgrade", "invoice", [], "POST", () =>
            window.location.replace("/billing/"),
        );
    });

    const prices: Prices = {
        annual: page_params.annual_price * (1 - page_params.percent_off / 100),
        monthly: page_params.monthly_price * (1 - page_params.percent_off / 100),
    };

    $<HTMLInputElement>("input[type=radio][name=license_management]").on("change", function () {
        helpers.show_license_section(this.value);
    });

    $<HTMLInputElement>("input[type=radio][name=schedule]").on("change", function () {
        helpers.update_charged_amount(prices, helpers.schedule_schema.parse(this.value));
    });

    $("#autopay_annual_price").text(helpers.format_money(prices.annual));
    $("#autopay_annual_price_per_month").text(helpers.format_money(prices.annual / 12));
    $("#autopay_monthly_price").text(helpers.format_money(prices.monthly));
    $("#invoice_annual_price").text(helpers.format_money(prices.annual));
    $("#invoice_annual_price_per_month").text(helpers.format_money(prices.annual / 12));

    helpers.show_license_section(
        $<HTMLInputElement>("input[type=radio][name=license_management]:checked").val()!,
    );
    helpers.update_charged_amount(
        prices,
        helpers.schedule_schema.parse(
            $<HTMLInputElement>("input[type=radio][name=schedule]:checked").val(),
        ),
    );
};

$(() => {
    initialize();
});
