import $ from "jquery";

import {page_params} from "../page_params";

import * as helpers from "./helpers";

export const initialize = () => {
    helpers.set_tab("upgrade");
    $("#add-card-button").on("click", (e) => {
        const license_management = $("input[type=radio][name=license_management]:checked").val();
        if (
            helpers.is_valid_input($(`#${CSS.escape(license_management)}_license_count`)) === false
        ) {
            return;
        }
        e.preventDefault();
        const success_callback = (response) => {
            window.location.replace(response.stripe_session_url);
        };
        helpers.create_ajax_request(
            "/json/billing/upgrade",
            "autopay",
            [],
            "POST",
            success_callback,
        );
    });

    $("#invoice-button").on("click", (e) => {
        if (helpers.is_valid_input($("#invoiced_licenses")) === false) {
            return;
        }
        e.preventDefault();
        helpers.create_ajax_request("/json/billing/upgrade", "invoice", [], "POST", () =>
            window.location.replace("/billing"),
        );
    });

    $("#sponsorship-button").on("click", (e) => {
        if (!helpers.is_valid_input($("#sponsorship-form"))) {
            return;
        }
        e.preventDefault();
        helpers.create_ajax_request("/json/billing/sponsorship", "sponsorship", [], "POST", () =>
            window.location.replace("/"),
        );
    });

    const prices = {};
    prices.annual = page_params.annual_price * (1 - page_params.percent_off / 100);
    prices.monthly = page_params.monthly_price * (1 - page_params.percent_off / 100);

    $("input[type=radio][name=license_management]").on("change", function () {
        helpers.show_license_section(this.value);
    });

    $("input[type=radio][name=schedule]").on("change", function () {
        helpers.update_charged_amount(prices, this.value);
    });

    $("select[name=organization-type]").on("change", (e) => {
        const string_value = $(e.currentTarget).find(":selected").attr("data-string-value");
        helpers.update_discount_details(string_value);
    });

    $("#autopay_annual_price").text(helpers.format_money(prices.annual));
    $("#autopay_annual_price_per_month").text(helpers.format_money(prices.annual / 12));
    $("#autopay_monthly_price").text(helpers.format_money(prices.monthly));
    $("#invoice_annual_price").text(helpers.format_money(prices.annual));
    $("#invoice_annual_price_per_month").text(helpers.format_money(prices.annual / 12));

    helpers.show_license_section($("input[type=radio][name=license_management]:checked").val());
    helpers.update_charged_amount(prices, $("input[type=radio][name=schedule]:checked").val());
};

$(() => {
    initialize();
});
