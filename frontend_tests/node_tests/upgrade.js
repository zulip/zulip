"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

const noop = () => {};
const template = fs.readFileSync("templates/corporate/upgrade.html", "utf-8");
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;

set_global("helpers", {
    set_tab: noop,
});

set_global("StripeCheckout", {
    configure: noop,
});

set_global("page_params", {
    annual_price: 8000,
    monthly_price: 800,
    seat_count: 8,
    percent_off: 20,
});

zrequire("helpers", "js/billing/helpers");
set_global("$", make_zjquery());

run_test("initialize", () => {
    let token_func;
    helpers.set_tab = (page_name) => {
        assert.equal(page_name, "upgrade");
    };

    let create_ajax_request_form_call_count = 0;
    helpers.create_ajax_request = (url, form_name, stripe_token, numeric_inputs, redirect_to) => {
        create_ajax_request_form_call_count += 1;
        if (form_name === "autopay") {
            assert.equal(url, "/json/billing/upgrade");
            assert.equal(stripe_token, "stripe_add_card_token");
            assert.deepEqual(numeric_inputs, ["licenses"]);
            assert.equal(redirect_to, undefined);
        } else if (form_name === "invoice") {
            assert.equal(url, "/json/billing/upgrade");
            assert.equal(stripe_token, undefined);
            assert.deepEqual(numeric_inputs, ["licenses"]);
            assert.equal(redirect_to, undefined);
        } else if (form_name === "sponsorship") {
            assert.equal(url, "/json/billing/sponsorship");
            assert.equal(stripe_token, undefined);
            assert.equal(numeric_inputs, undefined);
            assert.equal(redirect_to, "/");
        } else {
            throw new Error("Unhandled case");
        }
    };

    const open_func = (config_opts) => {
        assert.equal(config_opts.name, "Zulip");
        assert.equal(config_opts.zipCode, true);
        assert.equal(config_opts.billingAddress, true);
        assert.equal(config_opts.panelLabel, "Make payment");
        assert.equal(config_opts.label, "Add card");
        assert.equal(config_opts.allowRememberMe, false);
        assert.equal(config_opts.email, "{{ email }}");
        assert.equal(config_opts.description, "Zulip Cloud Standard");
        token_func("stripe_add_card_token");
    };

    StripeCheckout.configure = (config_opts) => {
        assert.equal(config_opts.image, "/static/images/logo/zulip-icon-128x128.png");
        assert.equal(config_opts.locale, "auto");
        assert.equal(config_opts.key, "{{ publishable_key }}");
        token_func = config_opts.token;

        return {
            open: open_func,
        };
    };

    helpers.show_license_section = (section) => {
        assert.equal(section, "automatic");
    };

    helpers.update_charged_amount = (prices, schedule) => {
        assert.equal(prices.annual, 6400);
        assert.equal(prices.monthly, 640);
        assert.equal(schedule, "monthly");
    };

    $("input[type=radio][name=license_management]:checked").val = () =>
        document.querySelector("input[type=radio][name=license_management]:checked").value;

    $("input[type=radio][name=schedule]:checked").val = () =>
        document.querySelector("input[type=radio][name=schedule]:checked").value;

    $("#autopay-form").data = (key) =>
        document.querySelector("#autopay-form").getAttribute("data-" + key);

    zrequire("upgrade", "js/billing/upgrade");

    const e = {
        preventDefault: noop,
    };

    const add_card_click_handler = $("#add-card-button").get_on_handler("click");
    const invoice_click_handler = $("#invoice-button").get_on_handler("click");
    const request_sponsorship_click_handler = $("#sponsorship-button").get_on_handler("click");

    helpers.is_valid_input = () => true;
    add_card_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 1);
    invoice_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 2);
    request_sponsorship_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 3);

    helpers.is_valid_input = () => false;
    add_card_click_handler(e);
    invoice_click_handler(e);
    request_sponsorship_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 3);

    helpers.show_license_section = (section) => {
        assert.equal(section, "manual");
    };
    const license_change_handler = $("input[type=radio][name=license_management]").get_on_handler(
        "change",
    );
    license_change_handler.call({value: "manual"});

    helpers.update_charged_amount = (prices, schedule) => {
        assert.equal(prices.annual, 6400);
        assert.equal(prices.monthly, 640);
        assert.equal(schedule, "monthly");
    };
    const schedule_change_handler = $("input[type=radio][name=schedule]").get_on_handler("change");
    schedule_change_handler.call({value: "monthly"});

    assert.equal($("#autopay_annual_price").text(), "64");
    assert.equal($("#autopay_annual_price_per_month").text(), "5.34");
    assert.equal($("#autopay_monthly_price").text(), "6.40");
    assert.equal($("#invoice_annual_price").text(), "64");
    assert.equal($("#invoice_annual_price_per_month").text(), "5.34");

    const organization_type_change_handler = $("select[name=organization-type]").get_on_handler(
        "change",
    );
    organization_type_change_handler.call({value: "open_source"});
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Open source projects are eligible for fully sponsored (free) Zulip Standard.",
    );
    organization_type_change_handler.call({value: "research"});
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Academic research organizations are eligible for fully sponsored (free) Zulip Standard.",
    );
    organization_type_change_handler.call({value: "event"});
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Events are eligible for fully sponsored (free) Zulip Standard.",
    );
    organization_type_change_handler.call({value: "education"});
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Education use is eligible for an 85%-100% discount.",
    );
    organization_type_change_handler.call({value: "non_profit"});
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Nonprofits are eligible for an 85%-100% discount.",
    );
    organization_type_change_handler.call({value: "other"});
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Your organization might be eligible for a discount or sponsorship.",
    );
});

run_test("autopay_form_fields", () => {
    assert.equal(document.querySelector("#autopay-form").dataset.key, "{{ publishable_key }}");
    assert.equal(document.querySelector("#autopay-form").dataset.email, "{{ email }}");
    assert.equal(
        document.querySelector("#autopay-form [name=seat_count]").value,
        "{{ seat_count }}",
    );
    assert.equal(
        document.querySelector("#autopay-form [name=signed_seat_count]").value,
        "{{ signed_seat_count }}",
    );
    assert.equal(document.querySelector("#autopay-form [name=salt]").value, "{{ salt }}");
    assert.equal(
        document.querySelector("#autopay-form [name=billing_modality]").value,
        "charge_automatically",
    );
    assert.equal(
        document.querySelector("#autopay-form #automatic_license_count").value,
        "{{ seat_count }}",
    );
    assert.equal(
        document.querySelector("#autopay-form #manual_license_count").min,
        "{{ seat_count }}",
    );

    const license_options = document.querySelectorAll(
        "#autopay-form input[type=radio][name=license_management]",
    );
    assert.equal(license_options.length, 2);
    assert.equal(license_options[0].value, "automatic");
    assert.equal(license_options[1].value, "manual");

    const schedule_options = document.querySelectorAll(
        "#autopay-form input[type=radio][name=schedule]",
    );
    assert.equal(schedule_options.length, 2);
    assert.equal(schedule_options[0].value, "monthly");
    assert.equal(schedule_options[1].value, "annual");

    assert(document.querySelector("#autopay-error"));
    assert(document.querySelector("#autopay-loading"));
    assert(document.querySelector("#autopay"));
    assert(document.querySelector("#autopay-success"));
    assert(document.querySelector("#autopay_loading_indicator"));

    assert(document.querySelector("input[name=csrfmiddlewaretoken]"));

    assert(document.querySelector("#free-trial-alert-message"));
});

run_test("invoice_form_fields", () => {
    assert.equal(
        document.querySelector("#invoice-form [name=signed_seat_count]").value,
        "{{ signed_seat_count }}",
    );
    assert.equal(document.querySelector("#invoice-form [name=salt]").value, "{{ salt }}");
    assert.equal(
        document.querySelector("#invoice-form [name=billing_modality]").value,
        "send_invoice",
    );
    assert.equal(
        document.querySelector("#invoice-form [name=licenses]").min,
        "{{ min_invoiced_licenses }}",
    );

    const schedule_options = document.querySelectorAll(
        "#invoice-form input[type=radio][name=schedule]",
    );
    assert.equal(schedule_options.length, 1);
    assert.equal(schedule_options[0].value, "annual");

    assert(document.querySelector("#invoice-error"));
    assert(document.querySelector("#invoice-loading"));
    assert(document.querySelector("#invoice"));
    assert(document.querySelector("#invoice-success"));
    assert(document.querySelector("#invoice_loading_indicator"));

    assert(document.querySelector("input[name=csrfmiddlewaretoken]"));

    assert(document.querySelector("#free-trial-alert-message"));
});
