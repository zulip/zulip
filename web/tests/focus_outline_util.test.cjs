"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const focus_outline_util = zrequire("focus_outline_util");

run_test("removes class on first navigation keypress", () => {
    const $container = $("#test-container");
    $container.addClass("no-visible-focus-outlines");

    assert.equal(focus_outline_util.maybe_show_focus_outlines($container, "tab"), true);
    assert.equal($container.hasClass("no-visible-focus-outlines"), false);
});

run_test("returns false when class already removed", () => {
    const $container = $("#test-container");
    // No class added — simulates second keypress.
    assert.equal(focus_outline_util.maybe_show_focus_outlines($container, "tab"), false);
});

run_test("returns false for non-navigation key", () => {
    const $container = $("#test-container");
    $container.addClass("no-visible-focus-outlines");

    assert.equal(focus_outline_util.maybe_show_focus_outlines($container, "enter"), false);
    // Class should not be removed.
    assert.equal($container.hasClass("no-visible-focus-outlines"), true);
});
