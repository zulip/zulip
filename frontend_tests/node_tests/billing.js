"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");

const {JSDOM} = require("jsdom");

const {mock_esm, set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const template = fs.readFileSync("templates/corporate/billing.html", "utf-8");
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;

const StripeCheckout = set_global("StripeCheckout", {
    configure: () => {},
});

const helpers = mock_esm("../../static/js/billing/helpers", {
    set_tab: () => {},
});

const billing = zrequire("billing/billing");

run_test("initialize", ({override}) => {
    let token_func;

    let set_tab_called = false;
    override(helpers, "set_tab", (page_name) => {
        assert.equal(page_name, "billing");
        set_tab_called = true;
    });

    let create_ajax_request_called = false;
    function card_change_ajax(
        url,
        form_name,
        stripe_token,
        ignored_inputs,
        method,
        success_callback,
    ) {
        assert.equal(url, "/json/billing/sources/change");
        assert.equal(form_name, "cardchange");
        assert.equal(stripe_token, "stripe_token");
        assert.deepEqual(ignored_inputs, []);
        assert.equal(method, "POST");
        window.location.replace = (new_location) => {
            assert.equal(new_location, "/billing");
        };
        success_callback();
        create_ajax_request_called = true;
    }

    let open_func_called = false;
    const open_func = (config_opts) => {
        assert.equal(config_opts.name, "Zulip");
        assert.equal(config_opts.zipCode, true);
        assert.equal(config_opts.billingAddress, true);
        assert.equal(config_opts.panelLabel, "Update card");
        assert.equal(config_opts.label, "Update card");
        assert.equal(config_opts.allowRememberMe, false);
        assert.equal(config_opts.email, "{{stripe_email}}");

        token_func("stripe_token");
        open_func_called = true;
    };

    let stripe_checkout_configure_called = false;
    override(StripeCheckout, "configure", (config_opts) => {
        assert.equal(config_opts.image, "/static/images/logo/zulip-icon-128x128.png");
        assert.equal(config_opts.locale, "auto");
        assert.equal(config_opts.key, "{{publishable_key}}");
        token_func = config_opts.token;
        stripe_checkout_configure_called = true;

        return {
            open: open_func,
        };
    });

    $("#payment-method").data = (key) =>
        document.querySelector("#payment-method").getAttribute("data-" + key);

    $.get_initialize_function()();

    assert.ok(set_tab_called);
    assert.ok(stripe_checkout_configure_called);
    const e = {
        preventDefault: () => {},
    };
    const update_card_click_handler = $("#update-card-button").get_on_handler("click");
    with_field(helpers, "create_ajax_request", card_change_ajax, () => {
        update_card_click_handler(e);
        assert.ok(create_ajax_request_called);
        assert.ok(open_func_called);
    });

    create_ajax_request_called = false;
    function plan_change_ajax(
        url,
        form_name,
        stripe_token,
        ignored_inputs,
        method,
        success_callback,
    ) {
        assert.equal(url, "/json/billing/plan");
        assert.equal(form_name, "planchange");
        assert.equal(stripe_token, undefined);
        assert.deepEqual(ignored_inputs, []);
        assert.equal(method, "PATCH");
        window.location.replace = (new_location) => {
            assert.equal(new_location, "/billing");
        };
        success_callback();
        create_ajax_request_called = true;
    }

    const change_plan_status_click_handler = $("#change-plan-status").get_on_handler("click");

    with_field(helpers, "create_ajax_request", plan_change_ajax, () => {
        change_plan_status_click_handler(e);
        assert.ok(create_ajax_request_called);
    });

    create_ajax_request_called = false;
    function license_change_ajax(
        url,
        form_name,
        stripe_token,
        ignored_inputs,
        method,
        success_callback,
    ) {
        assert.equal(url, "/json/billing/plan");
        assert.equal(form_name, "licensechange");
        assert.equal(stripe_token, undefined);
        assert.deepEqual(ignored_inputs, ["licenses_at_next_renewal"]);
        assert.equal(method, "PATCH");
        window.location.replace = (new_location) => {
            assert.equal(new_location, "/billing");
        };
        success_callback();
        create_ajax_request_called = true;
    }
    with_field(helpers, "create_ajax_request", license_change_ajax, () => {
        billing.create_update_license_request();
        assert.ok(create_ajax_request_called);
    });

    let create_update_license_request_called = false;
    override(billing, "create_update_license_request", () => {
        create_update_license_request_called = true;
    });

    const confirm_license_update_click_handler = $("#confirm-license-update-button").get_on_handler(
        "click",
    );
    confirm_license_update_click_handler(e);
    assert.ok(create_update_license_request_called);

    let confirm_license_modal_shown = false;
    override(helpers, "is_valid_input", () => true);
    $("#confirm-licenses-modal").modal = (action) => {
        assert.equal(action, "show");
        confirm_license_modal_shown = true;
    };
    $("#licensechange-input-section").data = (key) => {
        assert.equal(key, "licenses");
        return 20;
    };
    $("#new_licenses_input").val = () => 15;
    create_update_license_request_called = false;
    const update_licenses_button_click_handler =
        $("#update-licenses-button").get_on_handler("click");
    update_licenses_button_click_handler(e);
    assert.ok(create_update_license_request_called);
    assert.ok(!confirm_license_modal_shown);

    $("#new_licenses_input").val = () => 25;
    create_update_license_request_called = false;
    update_licenses_button_click_handler(e);
    assert.ok(!create_update_license_request_called);
    assert.ok(confirm_license_modal_shown);

    override(helpers, "is_valid_input", () => false);
    let prevent_default_called = false;
    const event = {
        prevent_default: () => {
            prevent_default_called = true;
        },
    };
    update_licenses_button_click_handler(event);
    assert.ok(!prevent_default_called);

    const update_next_renewal_licenses_button_click_handler = $(
        "#update-licenses-at-next-renewal-button",
    ).get_on_handler("click");
    create_ajax_request_called = false;
    function licenses_at_next_renewal_change_ajax(
        url,
        form_name,
        stripe_token,
        ignored_inputs,
        method,
        success_callback,
    ) {
        assert.equal(url, "/json/billing/plan");
        assert.equal(form_name, "licensechange");
        assert.equal(stripe_token, undefined);
        assert.deepEqual(ignored_inputs, ["licenses"]);
        assert.equal(method, "PATCH");
        window.location.replace = (new_location) => {
            assert.equal(new_location, "/billing");
        };
        success_callback();
        create_ajax_request_called = true;
    }
    with_field(helpers, "create_ajax_request", licenses_at_next_renewal_change_ajax, () => {
        update_next_renewal_licenses_button_click_handler(e);
        assert.ok(create_ajax_request_called);
    });
});

run_test("billing_template", () => {
    // Elements necessary for create_ajax_request
    assert.ok(document.querySelector("#cardchange-error"));
    assert.ok(document.querySelector("#cardchange-loading"));
    assert.ok(document.querySelector("#cardchange_loading_indicator"));
    assert.ok(document.querySelector("#cardchange-success"));

    assert.ok(document.querySelector("#licensechange-error"));
    assert.ok(document.querySelector("#licensechange-loading"));
    assert.ok(document.querySelector("#licensechange_loading_indicator"));
    assert.ok(document.querySelector("#licensechange-success"));

    assert.ok(document.querySelector("#planchange-error"));
    assert.ok(document.querySelector("#planchange-loading"));
    assert.ok(document.querySelector("#planchange_loading_indicator"));
    assert.ok(document.querySelector("#planchange-success"));

    assert.ok(document.querySelector("input[name=csrfmiddlewaretoken]"));
});
