"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");
const path = require("path");

const {JSDOM} = require("jsdom");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const jQueryFactory = require("./lib/real_jquery");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_billing_params");

const template = fs.readFileSync(
    path.resolve(__dirname, "../../templates/corporate/upgrade.html"),
    "utf8",
);
const dom = new JSDOM(template, {
    pretendToBeVisual: true,
    url: "http://zulip.zulipdev.com/upgrade/#billing",
});
const jquery = jQueryFactory(dom.window);

const history = set_global("history", {});
const loading = mock_esm("../src/loading");
set_global("document", {
    title: "Zulip",
});
const location = set_global("location", dom.window.location);

const helpers = zrequire("billing/helpers");

run_test("create_ajax_request", ({override}) => {
    const form_loading_indicator = "#invoice_loading_indicator";
    const form_input_section = "#invoice-input-section";
    const form_success = "#invoice-success";
    const form_error = "#invoice-error";
    const form_loading = "#invoice-loading";
    const zulip_limited_section = "#zulip-limited-section";
    const free_trial_alert_message = "#free-trial-alert-message";

    const state = {
        form_input_section_show: 0,
        form_input_section_hide: 0,
        form_error_show: 0,
        form_error_hide: 0,
        form_loading_show: 0,
        form_loading_hide: 0,
        form_success_show: 0,
        zulip_limited_section_show: 0,
        zulip_limited_section_hide: 0,
        free_trial_alert_message_hide: 0,
        free_trial_alert_message_show: 0,
        pushState: 0,
        make_indicator: 0,
    };

    loading.make_indicator = ($loading_indicator, config) => {
        assert.equal($loading_indicator.selector, form_loading_indicator);
        assert.equal(config.text, "Processing ...");
        assert.equal(config.abs_positioned, true);
        state.make_indicator += 1;
    };

    $(form_input_section).hide = () => {
        state.form_input_section_hide += 1;
    };

    $(form_input_section).show = () => {
        state.form_input_section_show += 1;
    };

    $(form_error).hide = () => {
        state.form_error_hide += 1;
    };

    $(form_error).show = () => {
        state.form_error_show += 1;
        return {
            text(msg) {
                assert.equal(msg, "response_message");
            },
        };
    };

    $(form_success).show = () => {
        state.form_success_show += 1;
    };

    $(form_loading).show = () => {
        state.form_loading_show += 1;
    };

    $(form_loading).hide = () => {
        state.form_loading_hide += 1;
    };

    $(zulip_limited_section).show = () => {
        state.zulip_limited_section_show += 1;
    };

    $(zulip_limited_section).hide = () => {
        state.zulip_limited_section_hide += 1;
    };

    $(free_trial_alert_message).show = () => {
        state.free_trial_alert_message_show += 1;
    };

    $(free_trial_alert_message).hide = () => {
        state.free_trial_alert_message_hide += 1;
    };

    $("#invoice-form").serializeArray = () => jquery("#invoice-form").serializeArray();

    let success_callback_called = false;
    const success_callback = (response) => {
        assert.equal(response.result, "success");
        success_callback_called = true;
    };
    override($, "ajax", ({type, url, data, success, error}) => {
        assert.equal(state.form_input_section_hide, 1);
        assert.equal(state.form_error_hide, 1);
        assert.equal(state.form_loading_show, 1);
        assert.equal(state.zulip_limited_section_hide, 1);
        assert.equal(state.zulip_limited_section_show, 0);
        assert.equal(state.free_trial_alert_message_hide, 1);
        assert.equal(state.free_trial_alert_message_show, 0);
        assert.equal(state.make_indicator, 1);

        assert.equal(type, "PATCH");
        assert.equal(url, "/json/billing/upgrade");

        assert.equal(Object.keys(data).length, 5);
        assert.equal(data.signed_seat_count, "{{ signed_seat_count }}");
        assert.equal(data.salt, "{{ salt }}");
        assert.equal(data.billing_modality, "send_invoice");
        assert.equal(data.schedule, "annual");
        assert.equal(data.licenses, "");

        assert.ok(!("license_management" in data));

        history.pushState = (state_object, title, path) => {
            state.pushState += 1;
            assert.equal(state_object, "");
            assert.equal(title, "Zulip");
            assert.equal(path, "/upgrade/");
        };

        success({result: "success"});

        assert.equal(state.pushState, 1);
        assert.equal(state.form_success_show, 1);
        assert.equal(state.form_error_hide, 2);
        assert.equal(state.form_loading_hide, 1);
        assert.equal(state.zulip_limited_section_hide, 1);
        assert.equal(state.zulip_limited_section_show, 0);
        assert.equal(state.free_trial_alert_message_hide, 1);
        assert.equal(state.free_trial_alert_message_show, 0);
        assert.ok(success_callback_called);

        error({responseJSON: {msg: "response_message"}});

        assert.equal(state.form_loading_hide, 2);
        assert.equal(state.form_error_show, 1);
        assert.equal(state.form_input_section_show, 1);
        assert.equal(state.zulip_limited_section_hide, 1);
        assert.equal(state.free_trial_alert_message_hide, 1);
        assert.equal(state.free_trial_alert_message_show, 1);
    });

    helpers.create_ajax_request(
        "/json/billing/upgrade",
        "invoice",
        ["license_management"],
        "PATCH",
        success_callback,
    );
});

run_test("format_money", () => {
    assert.equal(helpers.format_money("100"), "1");
    assert.equal(helpers.format_money("123.00"), "1.23");
    assert.equal(helpers.format_money("123.45"), "1.24");
    assert.equal(helpers.format_money("600"), "6");
    assert.equal(helpers.format_money("640"), "6.40");
    assert.equal(helpers.format_money("666.6666666666666"), "6.67");
    assert.equal(helpers.format_money("7600"), "76");
    assert.equal(helpers.format_money("8000"), "80");
    assert.equal(helpers.format_money("123416.323"), "1,234.17");
    assert.equal(helpers.format_money("927268238"), "9,272,682.38");
});

run_test("update_charged_amount", () => {
    const prices = {};
    prices.annual = 8000;
    prices.monthly = 800;
    page_params.seat_count = 35;

    // 80 * 35 = 2800
    helpers.update_charged_amount(prices, "annual");
    assert.equal($("#charged_amount").text(), "2,800");

    // 8 * 35 = 280
    helpers.update_charged_amount(prices, "monthly");
    assert.equal($("#charged_amount").text(), "280");
});

run_test("show_license_section", () => {
    const state = {
        show_license_automatic_section: 0,
        show_license_manual_section: 0,
        hide_license_automatic_section: 0,
        hide_license_manual_section: 0,
    };

    $("#license-automatic-section").show = () => {
        state.show_license_automatic_section += 1;
    };

    $("#license-manual-section").show = () => {
        state.show_license_manual_section += 1;
    };

    $("#license-automatic-section").hide = () => {
        state.hide_license_automatic_section += 1;
    };

    $("#license-manual-section").hide = () => {
        state.hide_license_manual_section += 1;
    };

    helpers.show_license_section("automatic");

    assert.equal(state.hide_license_automatic_section, 1);
    assert.equal(state.hide_license_manual_section, 1);
    assert.equal(state.show_license_automatic_section, 1);
    assert.equal(state.show_license_manual_section, 0);
    assert.equal($("#automatic_license_count").prop("disabled"), false);
    assert.equal($("#manual_license_count").prop("disabled"), true);

    helpers.show_license_section("manual");

    assert.equal(state.hide_license_automatic_section, 2);
    assert.equal(state.hide_license_manual_section, 2);
    assert.equal(state.show_license_automatic_section, 1);
    assert.equal(state.show_license_manual_section, 1);
    assert.equal($("#automatic_license_count").prop("disabled"), true);
    assert.equal($("#manual_license_count").prop("disabled"), false);
});

run_test("set_tab", () => {
    const state = {
        show_tab_billing: 0,
        show_tab_payment_method: 0,
        scrollTop: 0,
    };

    $('#upgrade-tabs.nav a[href="\\#billing"]').tab = (action) => {
        state.show_tab_billing += 1;
        assert.equal(action, "show");
    };

    $('#upgrade-tabs.nav a[href="\\#payment-method"]').tab = (action) => {
        state.show_tab_payment_method += 1;
        assert.equal(action, "show");
    };

    $("html").scrollTop = (val) => {
        state.scrollTop += 1;
        assert.equal(val, 0);
    };

    let hash_change_handler;
    window.addEventListener = (event, handler) => {
        assert.equal(event, "hashchange");
        hash_change_handler = handler;
    };

    location.hash = "#billing";
    helpers.set_tab("upgrade");
    assert.equal(state.show_tab_billing, 1);
    assert.equal(state.scrollTop, 1);

    const click_handler = $("#upgrade-tabs.nav-tabs a").get_on_handler("click");
    click_handler.call({hash: "#payment-method"});
    assert.equal(location.hash, "#payment-method");

    hash_change_handler();
    assert.equal(state.show_tab_payment_method, 1);
    assert.equal(state.scrollTop, 2);
});
