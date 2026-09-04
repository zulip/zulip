"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

mock_esm("../src/loading", {
    make_indicator: noop,
    destroy_indicator: noop,
});

const message_feed_loading = zrequire("message_feed_loading");
const {MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS} = message_feed_loading;

function is_loading() {
    return $(".top-messages-logo").hasClass("loading");
}

run_test("minimum display time", () => {
    message_feed_loading.show_loading_older();
    assert.ok(is_loading());

    // A fetch that finishes quickly leaves the indicator up until the
    // minimum display time has elapsed.
    clock.tick(100);
    message_feed_loading.hide_loading_older();
    assert.ok(is_loading());
    clock.tick(MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS - 100 - 1);
    assert.ok(is_loading());
    clock.tick(1);
    assert.ok(!is_loading());

    // A slow fetch hides the indicator right away.
    message_feed_loading.show_loading_older();
    clock.tick(MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS);
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

run_test("new fetch during pending hide", () => {
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    clock.tick(100);

    // Another fetch starts before the minimum time is up. The first
    // fetch's pending hide must not take the indicator down while
    // this one is still in flight, however long it takes.
    message_feed_loading.show_loading_older();
    clock.tick(MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS * 3);
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

run_test("hide_indicators hides immediately", () => {
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    message_feed_loading.hide_indicators();
    assert.ok(!is_loading());

    // The pending hide from before the reset must not affect a fetch
    // in the new narrow.
    message_feed_loading.show_loading_older();
    clock.tick(MIN_LOADING_OLDER_INDICATOR_DISPLAY_MS * 3);
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});
