"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const noop = () => {};

set_global("document", {});

const common = zrequire("common");

run_test("basics", () => {
    common.autofocus("#home");
    assert($("#home").is_focused());
});

run_test("phrase_match", () => {
    assert(common.phrase_match("tes", "test"));
    assert(common.phrase_match("Tes", "test"));
    assert(common.phrase_match("Tes", "Test"));
    assert(common.phrase_match("tes", "Stream Test"));

    assert(!common.phrase_match("tests", "test"));
    assert(!common.phrase_match("tes", "hostess"));
});

run_test("copy_data_attribute_value", (override) => {
    const admin_emails_val = "iago@zulip.com";

    const input = $.create("input");

    let removed;
    input.remove = () => {
        removed = true;
    };

    override(document, "createElement", () => input);
    override(document, "execCommand", noop);

    $("body").append = noop;
    $(input).val = (arg) => {
        assert.equal(arg, admin_emails_val);
        return {
            trigger: noop,
        };
    };

    const elem = {};
    let faded_in = false;
    let faded_out = false;

    elem.data = (key) => {
        assert.equal(key, "admin-emails");
        return admin_emails_val;
    };
    elem.fadeOut = (val) => {
        assert.equal(val, 250);
        faded_out = true;
    };
    elem.fadeIn = (val) => {
        assert.equal(val, 1000);
        faded_in = true;
    };
    common.copy_data_attribute_value(elem, "admin-emails");
    assert(removed);
    assert(faded_in);
    assert(faded_out);
});

run_test("adjust_mac_shortcuts non-mac", () => {
    common.has_mac_keyboard = () => false;

    // The adjust_mac_shortcuts has a really simple guard
    // at the top, and we just test the early-return behavior
    // by trying to pass it garbage.
    common.adjust_mac_shortcuts("selector-that-does-not-exist");
});

run_test("adjust_mac_shortcuts mac", () => {
    const keys_to_test_mac = new Map([
        ["Backspace", "Delete"],
        ["Enter", "Return"],
        ["Home", "Fn + ←"],
        ["End", "Fn + →"],
        ["PgUp", "Fn + ↑"],
        ["PgDn", "Fn + ↓"],
        ["X + Shift", "X + Shift"],
        ["⌘ + Return", "⌘ + Return"],
        ["Enter or Backspace", "Return or Delete"],
        ["Ctrl", "⌘"],
        ["Ctrl + Shift", "⌘ + Shift"],
        ["Ctrl + Backspace + End", "⌘ + Delete + Fn + →"],
    ]);

    common.has_mac_keyboard = () => true;

    const test_items = [];
    let key_no = 1;

    for (const [old_key, mac_key] of keys_to_test_mac) {
        const test_item = {};
        const stub = $.create("hotkey_" + key_no);
        stub.text(old_key);
        assert.equal(stub.hasClass("mac-cmd-key"), false);
        test_item.stub = stub;
        test_item.mac_key = mac_key;
        test_item.is_cmd_key = old_key.includes("Ctrl");
        test_items.push(test_item);
        key_no += 1;
    }

    const children = test_items.map((test_item) => ({to_$: () => test_item.stub}));

    $.create(".markdown_content", {children});

    const require_cmd = true;
    common.adjust_mac_shortcuts(".markdown_content", require_cmd);

    for (const test_item of test_items) {
        assert.equal(test_item.stub.hasClass("mac-cmd-key"), test_item.is_cmd_key);
        assert.equal(test_item.stub.text(), test_item.mac_key);
    }
});
