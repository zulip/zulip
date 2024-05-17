"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

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
