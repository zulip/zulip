"use strict";

set_global("$", global.make_zjquery());

zrequire("keydown_util");

run_test("test_early_returns", () => {
    const stub = $.create("stub");
    const opts = {
        elem: stub,
        handlers: {
            left_arrow: () => {
                throw new Error("do not dispatch this with alt key");
            },
        },
    };

    keydown_util.handle(opts);

    const e1 = {
        type: "keydown",
        which: 17, // not in keys
    };

    stub.trigger(e1);

    const e2 = {
        type: "keydown",
        which: 13, // no handler
    };

    stub.trigger(e2);

    const e3 = {
        type: "keydown",
        which: 37,
        altKey: true, // let browser handle
    };

    stub.trigger(e3);
});
