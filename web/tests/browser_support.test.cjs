"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../generated/supported_browser_regex.ts", {
    supportedBrowserRegex: /SupportedBrowser/,
});
const {is_browser_supported} = zrequire("browser_support");

run_test("matches supported browser", () => {
    window.navigator.userAgent = "Foo SupportedBrowser/1.0";
    assert.equal(is_browser_supported(), true);
});

run_test("rejects unsupported browser", () => {
    window.navigator.userAgent = "Foo OldBrowser/1.0";
    assert.equal(is_browser_supported(), false);
});
