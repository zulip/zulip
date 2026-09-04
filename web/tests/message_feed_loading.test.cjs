"use strict";

const assert = require("node:assert/strict");

const {clock, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const message_feed_loading = zrequire("message_feed_loading");
const {MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS} = message_feed_loading;

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

test("minimum display time", () => {
    message_feed_loading.show_loading_older();
    assert.ok(is_loading());

    // A fetch that finishes quickly leaves the indicator up until the
    // minimum display time has elapsed.
    clock.tick(100);
    message_feed_loading.hide_loading_older();
    assert.ok(is_loading());
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS - 100 - 1);
    assert.ok(is_loading());
    clock.tick(1);
    assert.ok(!is_loading());

    // A slow fetch hides the indicator right away.
    message_feed_loading.show_loading_older();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

test("new fetch during pending hide", () => {
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    clock.tick(100);

    // Another fetch starts before the minimum time is up. The first
    // fetch's pending hide must not take the indicator down while
    // this one is still in flight, however long it takes.
    message_feed_loading.show_loading_older();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS * 3);
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

test("hide_indicators hides immediately", () => {
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    message_feed_loading.hide_indicators();
    assert.ok(!is_loading());

    // The pending hide from before the reset must not affect a fetch
    // in the new narrow.
    message_feed_loading.show_loading_older();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS * 3);
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(!is_loading());
});

test("run_when_top_of_feed_indicator_hidden", () => {
    let runs = 0;
    const callback = () => {
        runs += 1;
    };

    // Nothing is showing, so the callback runs right away.
    message_feed_loading.run_when_top_of_feed_indicator_hidden(callback);
    assert.equal(runs, 1);

    // While the indicator is being kept on screen, the callback waits
    // until it is hidden.
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    message_feed_loading.run_when_top_of_feed_indicator_hidden(callback);
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS - 1);
    assert.equal(runs, 1);
    clock.tick(1);
    assert.ok(!is_loading());
    assert.equal(runs, 2);

    // Resetting for a new narrow drops callbacks from the old one.
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    message_feed_loading.run_when_top_of_feed_indicator_hidden(callback);
    message_feed_loading.hide_indicators();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    assert.equal(runs, 2);
});

test("initial page load and older fetches share the indicator", () => {
    message_feed_loading.show_loading_initial_page();
    assert.ok(is_loading());

    // A fetch for older messages that starts and finishes during the
    // initial page load does not take the indicator down.
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
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
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    assert.ok(!is_loading());
});

test("page load finishing during a fetch keeps the indicator", () => {
    message_feed_loading.show_loading_initial_page();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_initial_page();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    assert.ok(!is_loading());
});

test("older fetches are only shown while the top of the feed is in view", () => {
    set_top_of_feed_in_view(false);
    message_feed_loading.show_loading_older();
    assert.ok(!is_loading());

    // Scrolling the top of the feed into view during the fetch shows
    // the indicator, and its minimum display time starts then.
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS * 3);
    set_top_of_feed_in_view(true);
    message_feed_loading.update_for_scroll_position();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_older();
    assert.ok(is_loading());
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    assert.ok(!is_loading());

    // Scrolling it out of view hides the indicator right away, during
    // a fetch or while the indicator is still up for its minimum time
    // after one.
    message_feed_loading.show_loading_older();
    assert.ok(is_loading());
    set_top_of_feed_in_view(false);
    message_feed_loading.update_for_scroll_position();
    assert.ok(!is_loading());
    message_feed_loading.hide_loading_older();
    set_top_of_feed_in_view(true);
    message_feed_loading.show_loading_older();
    message_feed_loading.hide_loading_older();
    assert.ok(is_loading());
    set_top_of_feed_in_view(false);
    message_feed_loading.update_for_scroll_position();
    assert.ok(!is_loading());

    // Scrolling with no fetch in flight changes nothing.
    set_top_of_feed_in_view(true);
    message_feed_loading.update_for_scroll_position();
    assert.ok(!is_loading());

    // The initial page load is shown wherever the feed is scrolled to,
    // and scrolling does not hide it.
    set_top_of_feed_in_view(false);
    message_feed_loading.show_loading_initial_page();
    assert.ok(is_loading());
    message_feed_loading.update_for_scroll_position();
    assert.ok(is_loading());
    message_feed_loading.hide_loading_initial_page();
    clock.tick(MIN_TOP_OF_FEED_INDICATOR_DISPLAY_MS);
    assert.ok(!is_loading());
});
