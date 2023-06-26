"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");
const path = require("path");

const {JSDOM} = require("jsdom");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const template = fs.readFileSync(
    path.resolve(__dirname, "../../templates/corporate/billing.html"),
    "utf8",
);
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;
const location = set_global("location", {});

const helpers = mock_esm("../src/billing/helpers", {
    set_tab() {},
    set_sponsorship_form() {},
});

zrequire("billing/billing");

run_test("initialize", ({override}) => {
    let set_tab_called = false;
    override(helpers, "set_tab", (page_name) => {
        assert.equal(page_name, "billing");
        set_tab_called = true;
    });
    let set_sponsorship_form_called = false;
    override(helpers, "set_sponsorship_form", () => {
        set_sponsorship_form_called = true;
    });
    $.get_initialize_function()();
    assert.ok(set_tab_called);
    assert.ok(set_sponsorship_form_called);
});

run_test("card_update", ({override}) => {
    override(helpers, "set_tab", () => {});
    override(helpers, "stripe_session_url_schema", {
        parse(obj) {
            return obj;
        },
    });
    let create_ajax_request_called = false;
    function card_change_ajax(url, form_name, ignored_inputs, method, success_callback) {
        assert.equal(url, "/json/billing/session/start_card_update_session");
        assert.equal(form_name, "cardchange");
        assert.deepEqual(ignored_inputs, []);
        assert.equal(method, "POST");
        location.replace = (new_location) => {
            assert.equal(new_location, "https://stripe_session_url");
        };
        success_callback({stripe_session_url: "https://stripe_session_url"});
        create_ajax_request_called = true;
    }

    $.get_initialize_function()();

    const update_card_click_handler = $("#update-card-button").get_on_handler("click");
    override(helpers, "create_ajax_request", card_change_ajax);
    update_card_click_handler({preventDefault() {}});
    assert.ok(create_ajax_request_called);
});

run_test("planchange", ({override}) => {
    override(helpers, "set_tab", () => {});
    let create_ajax_request_called = false;
    function plan_change_ajax(url, form_name, ignored_inputs, method, success_callback) {
        assert.equal(url, "/json/billing/plan");
        assert.equal(form_name, "planchange");
        assert.deepEqual(ignored_inputs, []);
        assert.equal(method, "PATCH");
        location.replace = (new_location) => {
            assert.equal(new_location, "/billing/");
        };
        success_callback();
        create_ajax_request_called = true;
    }

    $.get_initialize_function()();
    const change_plan_status_click_handler = $("#change-plan-status").get_on_handler("click");

    override(helpers, "create_ajax_request", plan_change_ajax);
    change_plan_status_click_handler({preventDefault() {}});
    assert.ok(create_ajax_request_called);
});

run_test("licensechange", ({override}) => {
    override(helpers, "set_tab", () => {});
    let create_ajax_request_called = false;
    function license_change_ajax(url, form_name, ignored_inputs, method, success_callback) {
        assert.equal(url, "/json/billing/plan");
        assert.equal(form_name, "licensechange");
        assert.deepEqual(ignored_inputs, ["licenses_at_next_renewal"]);
        assert.equal(method, "PATCH");
        location.replace = (new_location) => {
            assert.equal(new_location, "/billing/");
        };
        success_callback();
        create_ajax_request_called = true;
    }
    override(helpers, "create_ajax_request", license_change_ajax);

    $.get_initialize_function()();

    const confirm_license_update_click_handler = $("#confirm-license-update-button").get_on_handler(
        "click",
    );
    confirm_license_update_click_handler({preventDefault() {}});
    assert.ok(create_ajax_request_called);

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
    create_ajax_request_called = false;
    const update_licenses_button_click_handler =
        $("#update-licenses-button").get_on_handler("click");
    update_licenses_button_click_handler({preventDefault() {}});
    assert.ok(create_ajax_request_called);
    assert.ok(!confirm_license_modal_shown);

    $("#new_licenses_input").val = () => 25;
    create_ajax_request_called = false;
    update_licenses_button_click_handler({preventDefault() {}});
    assert.ok(!create_ajax_request_called);
    assert.ok(confirm_license_modal_shown);

    override(helpers, "is_valid_input", () => false);
    const event = {
        /* istanbul ignore next */
        preventDefault() {
            throw new Error("unexpected preventDefault call");
        },
    };
    update_licenses_button_click_handler(event);

    const update_next_renewal_licenses_button_click_handler = $(
        "#update-licenses-at-next-renewal-button",
    ).get_on_handler("click");
    create_ajax_request_called = false;
    function licenses_at_next_renewal_change_ajax(
        url,
        form_name,
        ignored_inputs,
        method,
        success_callback,
    ) {
        assert.equal(url, "/json/billing/plan");
        assert.equal(form_name, "licensechange");
        assert.deepEqual(ignored_inputs, ["licenses"]);
        assert.equal(method, "PATCH");
        location.replace = (new_location) => {
            assert.equal(new_location, "/billing/");
        };
        success_callback();
        create_ajax_request_called = true;
    }
    override(helpers, "create_ajax_request", licenses_at_next_renewal_change_ajax);
    update_next_renewal_licenses_button_click_handler({preventDefault() {}});
    assert.ok(create_ajax_request_called);
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
