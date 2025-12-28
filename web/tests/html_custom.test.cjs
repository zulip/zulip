"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const h = zrequire("html");

const dom = new JSDOM(`<!DOCTYPE html>`);
set_global("document", dom.window.document);

run_test("ParenthesizedTag", () => {
    const tag = h.parenthesized_tag(h.span_tag({classes: ["empty"]}));
    assert.equal(tag.to_source(""), '(<span class="empty"></span>)');
    assert.equal(tag.as_raw_html(), '(<span class="empty"></span>)');
});
