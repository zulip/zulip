"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const sidebar_header_sticky_shadow = zrequire("sidebar_header_sticky_shadow");

function make_header(top) {
    const classes = new Set();
    return {
        getBoundingClientRect: () => ({top}),
        classList: {
            toggle(name, on) {
                if (on) {
                    classes.add(name);
                } else {
                    classes.delete(name);
                }
            },
            has: (name) => classes.has(name),
        },
    };
}

function make_scroll_container({scrollTop, container_top, headers}) {
    let scroll_listener;
    const container = {
        scrollTop,
        getBoundingClientRect: () => ({top: container_top}),
        querySelectorAll: () => headers,
        addEventListener(event, callback, options) {
            assert.equal(event, "scroll");
            assert.deepEqual(options, {passive: true});
            scroll_listener = callback;
        },
    };
    return {
        $wrapper: {length: 1, 0: container},
        get scroll_listener() {
            return scroll_listener;
        },
        container,
    };
}

run_test("install toggles shadow based on stickiness", ({override}) => {
    override(globalThis, "getComputedStyle", () => ({top: "40px"}));

    // Container has been scrolled; pin line is at container_top + sticky_top = 50.
    // Header sitting exactly at the pin line: stuck, shadow on.
    const stuck_header = make_header(50);
    // Header that has been pushed above the pin line by the next section
    // arriving from below; shadow suppressed to avoid a visible seam at
    // the junction.
    const pushed_out_header = make_header(45);
    // Header still below the pin line, not yet stuck.
    const below_pin_line_header = make_header(500);

    const scroll = make_scroll_container({
        scrollTop: 120,
        container_top: 10,
        headers: [stuck_header, pushed_out_header, below_pin_line_header],
    });

    sidebar_header_sticky_shadow.initialize(scroll.$wrapper, ".header");

    assert.ok(stuck_header.classList.has("sidebar-header-drop-shadow"));
    assert.ok(!pushed_out_header.classList.has("sidebar-header-drop-shadow"));
    assert.ok(!below_pin_line_header.classList.has("sidebar-header-drop-shadow"));

    // The scroll listener re-runs the update logic.
    assert.ok(typeof scroll.scroll_listener === "function");
    scroll.scroll_listener();
    assert.ok(stuck_header.classList.has("sidebar-header-drop-shadow"));
});

run_test("install leaves shadow off before any scroll", ({override}) => {
    override(globalThis, "getComputedStyle", () => ({top: "40px"}));

    // Same geometry as the stuck case above (header top=50, pin line=50),
    // but scrollTop=0. Pre-set the shadow class so we can see install()
    // actively removes it, proving the has_scrolled guard is doing its job.
    const header = make_header(50);
    header.classList.toggle("sidebar-header-drop-shadow", true);
    const scroll = make_scroll_container({
        scrollTop: 0,
        container_top: 10,
        headers: [header],
    });

    sidebar_header_sticky_shadow.initialize(scroll.$wrapper, ".header");
    assert.ok(!header.classList.has("sidebar-header-drop-shadow"));
});

run_test("install handles missing computed top", ({override}) => {
    override(globalThis, "getComputedStyle", () => ({top: "auto"}));

    // With sticky_top defaulting to 0, a header at container_top is stuck.
    const container_top = 10;
    const header = make_header(container_top);
    const scroll = make_scroll_container({
        scrollTop: 50,
        container_top,
        headers: [header],
    });

    sidebar_header_sticky_shadow.initialize(scroll.$wrapper, ".header");
    assert.ok(header.classList.has("sidebar-header-drop-shadow"));
});
