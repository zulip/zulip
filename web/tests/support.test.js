"use strict";

const {strict: assert} = require("assert");
const fs = require("fs");
const path = require("path");

const {JSDOM} = require("jsdom");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const template = fs.readFileSync(
    path.resolve(__dirname, "../../templates/analytics/realm_details.html"),
    "utf8",
);
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;

zrequire("../src/analytics/support");

run_test("scrub_realm", () => {
    $.get_initialize_function()();
    const click_handler = $("body").get_on_handler("click", ".scrub-realm-button");

    const $fake_this = $.create("fake-.scrub-realm-button");
    $fake_this.attr = (name) => {
        assert.equal(name, "data-string-id");
        return "zulip";
    };

    let submit_form_called = false;
    $fake_this.form = {
        submit() {
            submit_form_called = true;
        },
    };
    const event = {
        preventDefault() {},
    };

    window.prompt = () => "zulip";
    click_handler.call($fake_this, event);
    assert.ok(submit_form_called);

    submit_form_called = false;
    window.prompt = () => "invalid-string-id";
    let alert_called = false;
    window.alert = () => {
        alert_called = true;
    };
    click_handler.call($fake_this, event);
    assert.ok(!submit_form_called);
    assert.ok(alert_called);

    assert.equal(typeof click_handler, "function");

    assert.equal(document.querySelectorAll(".scrub-realm-button").length, 1);
});
