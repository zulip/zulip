"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const resize = zrequire("resize");

run_test("watch_compose_box_for_virtual_keyboard - no visualViewport", () => {
    set_global("window", {
        visualViewport: undefined,
        innerHeight: 800,
    });
    // Should not throw when visualViewport is not supported
    resize.watch_compose_box_for_virtual_keyboard();
    resize.unwatch_compose_box_for_virtual_keyboard();
});

run_test("watch_compose_box_for_virtual_keyboard - attaches and removes listener", () => {
    let attached_handler = null;
    let removed_handler = null;

    const mock_visual_viewport = {
        height: 500,
        offsetTop: 0,
        addEventListener(event, handler) {
            assert.equal(event, "resize");
            attached_handler = handler;
        },
        removeEventListener(event, handler) {
            assert.equal(event, "resize");
            removed_handler = handler;
        },
    };

    set_global("window", {
        visualViewport: mock_visual_viewport,
        innerHeight: 800,
    });

    resize.watch_compose_box_for_virtual_keyboard();
    assert.ok(attached_handler !== null, "resize listener should be attached");

    // Calling again should be no-op (guard check)
    const first_handler = attached_handler;
    resize.watch_compose_box_for_virtual_keyboard();
    assert.equal(attached_handler, first_handler, "should not attach again");

    // Remove listener
    resize.unwatch_compose_box_for_virtual_keyboard();
    assert.equal(removed_handler, first_handler, "same handler should be removed");
});
