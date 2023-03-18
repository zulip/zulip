"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");
const path = require("path");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_billing_params");

const noop = () => {};
const template = fs.readFileSync(
    path.resolve(__dirname, "../../templates/corporate/upgrade.html"),
    "utf8",
);
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;
const location = set_global("location", {});

const helpers = zrequire("../src/billing/helpers");
zrequire("../src/billing/upgrade");

run_test("initialize", ({override_rewire}) => {
    page_params.annual_price = 8000;
    page_params.monthly_price = 800;
    page_params.seat_count = 8;
    page_params.percent_off = 20;

    override_rewire(helpers, "set_tab", (page_name) => {
        assert.equal(page_name, "upgrade");
    });

    let create_ajax_request_form_call_count = 0;
    helpers.__Rewire__(
        "create_ajax_request",
        (url, form_name, ignored_inputs, type, success_callback) => {
            create_ajax_request_form_call_count += 1;
            switch (form_name) {
                case "autopay":
                    assert.equal(url, "/json/billing/upgrade");
                    assert.deepEqual(ignored_inputs, []);
                    assert.equal(type, "POST");
                    location.replace = (new_location) => {
                        assert.equal(new_location, "https://stripe_session_url");
                    };
                    // mock redirectToCheckout and verify its called
                    success_callback({stripe_session_url: "https://stripe_session_url"});
                    break;
                case "invoice":
                    assert.equal(url, "/json/billing/upgrade");
                    assert.deepEqual(ignored_inputs, []);
                    assert.equal(type, "POST");
                    location.replace = (new_location) => {
                        assert.equal(new_location, "/billing/");
                    };
                    success_callback();
                    break;
                case "sponsorship":
                    assert.equal(url, "/json/billing/sponsorship");
                    assert.deepEqual(ignored_inputs, []);
                    assert.equal(type, "POST");
                    location.replace = (new_location) => {
                        assert.equal(new_location, "/");
                    };
                    success_callback();
                    break;
                /* istanbul ignore next */
                default:
                    throw new Error("Unhandled case");
            }
        },
    );

    override_rewire(helpers, "show_license_section", (section) => {
        assert.equal(section, "automatic");
    });

    override_rewire(helpers, "update_charged_amount", (prices, schedule) => {
        assert.equal(prices.annual, 6400);
        assert.equal(prices.monthly, 640);
        assert.equal(schedule, "monthly");
    });

    $("input[type=radio][name=license_management]:checked").val = () =>
        document.querySelector("input[type=radio][name=license_management]:checked").value;

    $("input[type=radio][name=schedule]:checked").val = () =>
        document.querySelector("input[type=radio][name=schedule]:checked").value;

    const initialize_function = $.get_initialize_function();
    initialize_function();

    const e = {
        preventDefault: noop,
    };

    const add_card_click_handler = $("#add-card-button").get_on_handler("click");
    const invoice_click_handler = $("#invoice-button").get_on_handler("click");
    const request_sponsorship_click_handler = $("#sponsorship-button").get_on_handler("click");

    override_rewire(helpers, "is_valid_input", () => true);
    add_card_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 1);
    invoice_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 2);
    request_sponsorship_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 3);

    override_rewire(helpers, "is_valid_input", () => false);
    add_card_click_handler(e);
    invoice_click_handler(e);
    request_sponsorship_click_handler(e);
    assert.equal(create_ajax_request_form_call_count, 3);

    override_rewire(helpers, "show_license_section", (section) => {
        assert.equal(section, "manual");
    });
    const license_change_handler = $("input[type=radio][name=license_management]").get_on_handler(
        "change",
    );
    license_change_handler.call({value: "manual"});

    override_rewire(helpers, "update_charged_amount", (prices, schedule) => {
        assert.equal(prices.annual, 6400);
        assert.equal(prices.monthly, 640);
        assert.equal(schedule, "monthly");
    });
    const schedule_change_handler = $("input[type=radio][name=schedule]").get_on_handler("change");
    schedule_change_handler.call({value: "monthly"});

    assert.equal($("#autopay_annual_price").text(), "64");
    assert.equal($("#autopay_annual_price_per_month").text(), "5.34");
    assert.equal($("#autopay_monthly_price").text(), "6.40");
    assert.equal($("#invoice_annual_price").text(), "64");
    assert.equal($("#invoice_annual_price_per_month").text(), "5.34");

    helpers.update_discount_details("opensource");
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Zulip Cloud Standard is free for open-source projects.",
    );
    helpers.update_discount_details("research");
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Zulip Cloud Standard is free for academic research.",
    );
    helpers.update_discount_details("event");
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Zulip Cloud Standard is free for academic conferences and most non-profit events.",
    );
    helpers.update_discount_details("education");
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Zulip Cloud Standard is discounted 85% for education.",
    );
    helpers.update_discount_details("nonprofit");
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Zulip Cloud Standard is discounted 85%+ for registered non-profits.",
    );
    helpers.update_discount_details("other");
    assert.equal(
        $("#sponsorship-discount-details").text(),
        "Your organization may be eligible for a discount on Zulip Cloud Standard. Organizations whose members are not employees are generally eligible.",
    );
});

run_test("autopay_form_fields", () => {
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

    assert.ok(document.querySelector("#autopay-error"));
    assert.ok(document.querySelector("#autopay-loading"));
    assert.ok(document.querySelector("#autopay"));
    assert.ok(document.querySelector("#autopay-success"));
    assert.ok(document.querySelector("#autopay_loading_indicator"));

    assert.ok(document.querySelector("input[name=csrfmiddlewaretoken]"));

    assert.ok(document.querySelector("#free-trial-alert-message"));
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

    assert.ok(document.querySelector("#invoice-error"));
    assert.ok(document.querySelector("#invoice-loading"));
    assert.ok(document.querySelector("#invoice"));
    assert.ok(document.querySelector("#invoice-success"));
    assert.ok(document.querySelector("#invoice_loading_indicator"));

    assert.ok(document.querySelector("input[name=csrfmiddlewaretoken]"));

    assert.ok(document.querySelector("#free-trial-alert-message"));
});
