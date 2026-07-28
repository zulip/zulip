"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const navigator = set_global("navigator", {platform: ""});

const keydown_util = zrequire("keydown_util");

run_test("test_early_returns", () => {
    const $stub = $.create("stub");
    const opts = {
        $elem: $stub,
        handlers: {
            /* istanbul ignore next */
            ArrowLeft() {
                throw new Error("do not dispatch this with alt key");
            },
        },
    };

    keydown_util.handle(opts);

    const e1 = {
        type: "keydown",
        key: "a", // not in keys
    };

    $stub.trigger(e1);

    const e2 = {
        type: "keydown",
        key: "Enter", // no handler
    };

    $stub.trigger(e2);

    const e3 = {
        type: "keydown",
        key: "ArrowLeft",
        altKey: true, // let browser handle
    };

    $stub.trigger(e3);
});

run_test("get_mac_ctrl_navigation_key", () => {
    navigator.platform = "MacIntel";

    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({key: "n", code: "KeyN", ctrlKey: true}),
        "ArrowDown",
    );
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({key: "p", code: "KeyP", ctrlKey: true}),
        "ArrowUp",
    );

    // Caps Lock and non-Latin keyboard layouts should not affect the shortcuts.
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({key: "N", code: "KeyN", ctrlKey: true}),
        "ArrowDown",
    );
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({key: "т", code: "KeyN", ctrlKey: true}),
        "ArrowDown",
    );
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({key: "з", code: "KeyP", ctrlKey: true}),
        "ArrowUp",
    );

    // Ctrl must be the only modifier key pressed.
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({
            key: "n",
            code: "KeyN",
            ctrlKey: true,
            shiftKey: true,
        }),
        undefined,
    );
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({
            key: "n",
            code: "KeyN",
            ctrlKey: true,
            altKey: true,
        }),
        undefined,
    );
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({
            key: "n",
            code: "KeyN",
            ctrlKey: true,
            metaKey: true,
        }),
        undefined,
    );

    navigator.platform = "Linux x86_64";
    assert.equal(
        keydown_util.get_mac_ctrl_navigation_key({key: "n", code: "KeyN", ctrlKey: true}),
        undefined,
    );

    navigator.platform = "";
});

run_test("test_ime_enter_events", () => {
    // these events shouldn't be recognized as a return keypress.
    const event_1 = {
        key: "Enter",
        originalEvent: {
            isComposing: true,
        },
    };

    const event_2 = {
        key: "Random",
        originalEvent: {
            isComposing: false,
        },
    };
    assert.ok(!keydown_util.is_enter_event(event_1));
    assert.ok(!keydown_util.is_enter_event(event_2));

    // these are valid return keypress events.
    const event_3 = {
        key: "Enter",
        originalEvent: {
            isComposing: false,
        },
    };
    const event_4 = {
        key: "Enter",
        // Edgacase: if there is no originalEvent, JQuery didn't provide the object.
    };
    assert.ok(keydown_util.is_enter_event(event_3));
    assert.ok(keydown_util.is_enter_event(event_4));
});
