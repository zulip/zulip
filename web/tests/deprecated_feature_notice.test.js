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
        'translated HTML: We\'ve replaced the "Shift + C" hotkey with "X" to make this common shortcut easier to trigger.';
    const actual = deprecated_feature_notice.get_hotkey_deprecation_notice("Shift + C", "X");
    assert.equal(actual, expected);
});
