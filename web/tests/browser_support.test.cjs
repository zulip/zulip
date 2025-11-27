"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../generated/supported_browser_regex.ts", {
    baselineBrowserRegex: /BaselineBrowser/,
    allBrowsersRegex: /(BaselineBrowser|OldUnsupportedBrowser)/,
});
const {is_browser_supported} = zrequire("browser_support");

run_test("matches browser present in baseline browsers", () => {
    window.navigator.userAgent = "Foo BaselineBrowser/1.0";
    assert.equal(is_browser_supported(), true);
});

run_test("rejects browser present in all browsers but not in baseline browsers", () => {
    window.navigator.userAgent = "Foo OldUnsupportedBrowser/1.0";
    assert.equal(is_browser_supported(), false);
});

run_test("browser not present in all browsers is skipped for checking", () => {
    window.navigator.userAgent = "Foo ExperimentalBrowser/1.0";
    assert.equal(is_browser_supported(), true);
});
