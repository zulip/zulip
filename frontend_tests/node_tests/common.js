"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

const noop = () => {};

set_global("$", make_zjquery());
const input = $.create("input");
set_global("document", {
    createElement: () => input,
    execCommand: noop,
});

$("body").append = noop;
$(input).val = (arg) => {
    assert.equal(arg, "iago@zulip.com");
    return {
        trigger: noop,
    };
};

zrequire("common");

function get_key_stub_html(key_text, expected_key, obj_name) {
    const key_stub = $.create(obj_name);
    key_stub.text(key_text);
    key_stub.expected_key = function () {
        return expected_key;
    };
    return key_stub;
}

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

run_test("copy_data_attribute_value", () => {
    const elem = $.create(".envelope-link");
    elem.data = (key) => {
        if (key === "admin-emails") {
            return "iago@zulip.com";
        }
        return "";
    };
    elem.fadeOut = (val) => {
        assert.equal(val, 250);
    };
    elem.fadeIn = (val) => {
        assert.equal(val, 1000);
    };
    common.copy_data_attribute_value(elem, "admin-emails");
});

run_test("adjust_mac_shortcuts", () => {
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
    const keys_to_test_non_mac = new Map([
        ["Backspace", "Backspace"],
        ["Enter", "Enter"],
        ["Home", "Home"],
        ["End", "End"],
        ["PgUp", "PgUp"],
        ["PgDn", "PgDn"],
        ["X + Shift", "X + Shift"],
        ["⌘ + Return", "⌘ + Return"],
        ["Ctrl + Shift", "Ctrl + Shift"],
        ["Ctrl + Backspace + End", "Ctrl + Backspace + End"],
    ]);

    let key_no;
    let keys_elem_list = [];

    common.has_mac_keyboard = function () {
        return false;
    };
    key_no = 1;
    for (const [key, value] of keys_to_test_non_mac) {
        keys_elem_list.push(get_key_stub_html(key, value, "hotkey_non_mac_" + key_no));
        key_no += 1;
    }

    common.adjust_mac_shortcuts(".markdown_content");
    for (const key_elem of keys_elem_list) {
        assert(key_elem.text(), key_elem.expected_key());
    }

    keys_elem_list = [];
    key_no = 1;
    common.has_mac_keyboard = function () {
        return true;
    };
    for (const [key, value] of keys_to_test_mac) {
        keys_elem_list.push(get_key_stub_html(key, value, "hotkey_" + key_no));
        key_no += 1;
    }

    $(".markdown_content").each = (f) => {
        for (const key_elem of keys_elem_list) {
            f.call(key_elem);
        }
    };
    common.adjust_mac_shortcuts(".markdown_content");
    for (const key_elem of keys_elem_list) {
        assert.equal(key_elem.text(), key_elem.expected_key());
    }

    const markdown_hotkey_1 = get_key_stub_html(
        "Ctrl + Backspace",
        "⌘ + Delete",
        "markdown_hotkey_1",
    );
    $(".markdown_content").each = (f) => {
        f.call(markdown_hotkey_1);
    };
    common.adjust_mac_shortcuts(".markdown_content", true);
    assert.equal(markdown_hotkey_1.text(), markdown_hotkey_1.expected_key());
    assert.equal(markdown_hotkey_1.hasClass("mac-cmd-key"), true);
});
