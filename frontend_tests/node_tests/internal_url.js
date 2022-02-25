"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const internal_url = zrequire("../shared/js/internal_url");

run_test("test encodeHashComponent", () => {
    const decoded = "https://www.zulipexample.com";
    const encoded = "https.3A.2F.2Fwww.2Ezulipexample.2Ecom";
    const result = internal_url.encodeHashComponent(decoded);
    assert.equal(result, encoded);
});

run_test("test decodeHashComponent", () => {
    const decoded = "https://www.zulipexample.com";
    const encoded = "https.3A.2F.2Fwww.2Ezulipexample.2Ecom";
    const result = internal_url.decodeHashComponent(encoded);
    assert.equal(result, decoded);
});
