"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const message_feed_loading = zrequire("message_feed_loading");

function is_loading() {
    return $("#top_of_feed_loading_indicator").hasClass("loading");
}

run_test("initial page load and older fetches share the indicator", () => {
    message_feed_loading.show_loading_initial_page();
    assert.ok(is_loading());

    // A fetch for older messages that starts and finishes during the
    // initial page load does not take the indicator down.
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    assert.ok(is_loading());

    // Nor does resetting the UI for a new narrow.
    message_feed_loading.hide_indicators();
    assert.ok(is_loading());

    message_feed_loading.hide_loading_initial_page();
    assert.ok(!is_loading());

    // Once the page has loaded, the indicator follows the fetches.
    message_feed_loading.show_loading_older();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

run_test("page load finishing during a fetch keeps the indicator", () => {
    message_feed_loading.show_loading_initial_page();
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_initial_page();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});
