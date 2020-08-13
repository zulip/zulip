"use strict";

const fs = require("fs");

const {JSDOM} = require("jsdom");

const template = fs.readFileSync("templates/analytics/realm_details.html", "utf-8");
const dom = new JSDOM(template, {pretendToBeVisual: true});
const document = dom.window.document;

let jquery_init;
global.$ = (f) => {
    jquery_init = f;
};
zrequire("support", "js/analytics/support");
set_global("$", global.make_zjquery());

run_test("scrub_realm", () => {
    jquery_init();
    const click_handler = $("body").get_on_handler("click", ".scrub-realm-button");

    const fake_this = $.create("fake-.scrub-realm-button");
    fake_this.data = (name) => {
        assert.equal(name, "string-id");
        return "zulip";
    };

    let submit_form_called = false;
    fake_this.form = {
        submit: () => {
            submit_form_called = true;
        },
    };
    const event = {
        preventDefault: () => {},
    };

    window.prompt = () => "zulip";
    click_handler.call(fake_this, event);
    assert(submit_form_called);

    submit_form_called = false;
    window.prompt = () => "invalid-string-id";
    let alert_called = false;
    window.alert = () => {
        alert_called = true;
    };
    click_handler.call(fake_this, event);
    assert(!submit_form_called);
    assert(alert_called);

    assert.equal(typeof click_handler, "function");

    assert.equal(document.querySelectorAll(".scrub-realm-button").length, 1);
});
