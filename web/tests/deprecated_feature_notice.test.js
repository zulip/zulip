"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

set_global("navigator", {
    userAgent: "",
});

const deprecated_feature_notice = zrequire("deprecated_feature_notice");

run_test("get_hotkey_deprecation_notice", () => {
    const expected =
        'translated HTML: We\'ve replaced the "*" hotkey with "Ctrl + s" to make this common shortcut easier to trigger.';
    const actual = deprecated_feature_notice.get_hotkey_deprecation_notice("*", "Ctrl + s");
    assert.equal(actual, expected);
});

run_test("get_hotkey_deprecation_notice_mac", () => {
    navigator.userAgent =
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.167 Safari/537.36";
    const expected =
        'translated HTML: We\'ve replaced the "*" hotkey with "Cmd + s" to make this common shortcut easier to trigger.';
    const actual = deprecated_feature_notice.get_hotkey_deprecation_notice("*", "Cmd + s");
    assert.equal(actual, expected);
    // Reset userAgent
    navigator.userAgent = "";
});
