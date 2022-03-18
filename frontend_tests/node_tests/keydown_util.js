"use strict";

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const keydown_util = zrequire("keydown_util");

run_test("test_early_returns", () => {
    const $stub = $.create("stub");
    const opts = {
        $elem: $stub,
        handlers: {
            ArrowLeft: () => {
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
