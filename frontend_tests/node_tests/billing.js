"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");

const {JSDOM} = require("jsdom");

const {set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const template = fs.readFileSync("templates/corporate/billing.html", "utf-8");
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;

const helpers = set_global("helpers", {
    set_tab: () => {},
});
const StripeCheckout = set_global("StripeCheckout", {
    configure: () => {},
});

run_test("initialize", (override) => {
    let token_func;

    let set_tab_called = false;
    override(helpers, "set_tab", (page_name) => {
        assert.equal(page_name, "billing");
        set_tab_called = true;
    });

    let create_ajax_request_called = false;
    function card_change_ajax(url, form_name, stripe_token) {
        assert.equal(url, "/json/billing/sources/change");
        assert.equal(form_name, "cardchange");
        assert.equal(stripe_token, "stripe_token");
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

    zrequire("billing", "js/billing/billing");

    assert(set_tab_called);
    assert(stripe_checkout_configure_called);
    const e = {
        preventDefault: () => {},
    };
    const update_card_click_handler = $("#update-card-button").get_on_handler("click");
    with_field(helpers, "create_ajax_request", card_change_ajax, () => {
        update_card_click_handler(e);
        assert(create_ajax_request_called);
        assert(open_func_called);
    });

    create_ajax_request_called = false;
    function plan_change_ajax(url, form_name, stripe_token, numeric_inputs) {
        assert.equal(url, "/json/billing/plan/change");
        assert.equal(form_name, "planchange");
        assert.equal(stripe_token, undefined);
        assert.deepEqual(numeric_inputs, ["status"]);
        create_ajax_request_called = true;
    }

    const change_plan_status_click_handler = $("#change-plan-status").get_on_handler("click");

    with_field(helpers, "create_ajax_request", plan_change_ajax, () => {
        change_plan_status_click_handler(e);
    });
    assert(create_ajax_request_called);
});

run_test("billing_template", () => {
    // Elements necessary for create_ajax_request
    assert(document.querySelector("#cardchange-error"));
    assert(document.querySelector("#cardchange-loading"));
    assert(document.querySelector("#cardchange_loading_indicator"));
    assert(document.querySelector("#cardchange-success"));

    assert(document.querySelector("input[name=csrfmiddlewaretoken]"));
});
