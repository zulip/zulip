"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const message_feed_loading = zrequire("message_feed_loading");

function is_loading() {
    return $("#top_of_feed_loading_indicator").hasClass("loading");
}

// The indicator sticks to the bottom of the navbar once the top of the
// feed has scrolled up past it.
function set_top_of_feed_in_view(in_view) {
    window.scrollY = in_view ? 0 : 400;
}

function test(label, f) {
    run_test(label, (helpers) => {
        set_top_of_feed_in_view(true);
        f(helpers);
    });
}

test("initial page load and older fetches share the indicator", () => {
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

test("page load finishing during a fetch keeps the indicator", () => {
    message_feed_loading.show_loading_initial_page();
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_initial_page();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

test("older fetches are only shown while the top of the feed is in view", () => {
    set_top_of_feed_in_view(false);
    message_feed_loading.show_loading_older();
    assert.ok(!is_loading());

    // Scrolling the top of the feed into view during the fetch shows
    // the indicator.
    set_top_of_feed_in_view(true);
    message_feed_loading.update_for_scroll_position();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());

    // Scrolling it out of view during a fetch hides the indicator.
    message_feed_loading.show_loading_older();
    assert.ok(is_loading());
    set_top_of_feed_in_view(false);
    message_feed_loading.update_for_scroll_position();
    assert.ok(!is_loading());
    message_feed_loading.hide_loading_older();

    // Scrolling with no fetch in flight changes nothing.
    set_top_of_feed_in_view(true);
    message_feed_loading.update_for_scroll_position();
    assert.ok(!is_loading());

    // The initial page load is shown wherever the feed is scrolled to.
    set_top_of_feed_in_view(false);
    message_feed_loading.show_loading_initial_page();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_initial_page();
    assert.ok(!is_loading());
});
