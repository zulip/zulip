"use strict";

const assert = require("node:assert/strict");

const MockDate = require("mockdate");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

let time = 0;
let checker;
MockDate.set(time);

function advance_secs(secs) {
    time += secs * 1000;
    MockDate.set(time);
}

set_global("setInterval", (f, interval) => {
    checker = f;
    assert.equal(interval, 5000);
});

let resume_handler;
let pageshow_handler;

set_global("document", {
    addEventListener(event, handler) {
        if (event === "resume") {
            resume_handler = handler;
        }
    },
});

set_global("window", {
    addEventListener(event, handler) {
        if (event === "pageshow") {
            pageshow_handler = handler;
        }
    },
});

run_test("basics", () => {
    const watchdog = zrequire("watchdog");
    watchdog._reset_for_testing();
    watchdog.initialize();
    // Test without callbacks first.
    checker();
    advance_secs(5);
    checker();

    let num_times_called_back = 0;

    function callback() {
        num_times_called_back += 1;
    }

    watchdog.on_unsuspend(callback);

    // Simulate healthy operation.
    advance_secs(5);
    checker();
    assert.equal(num_times_called_back, 0);

    // Simulate machine going to sleep.
    advance_secs(81);
    checker();
    assert.equal(num_times_called_back, 1);

    // Simulate healthy operations resume, and
    // explicitly call check_for_unsuspend.
    num_times_called_back = 0;
    advance_secs(5);
    watchdog.check_for_unsuspend();
    assert.equal(num_times_called_back, 0);

    // Simulate another suspension.
    advance_secs(100);
    watchdog.check_for_unsuspend();
    assert.equal(num_times_called_back, 1);

    // Error while executing callback
    num_times_called_back = 0;
    advance_secs(100);
    watchdog.on_unsuspend(() => {
        num_times_called_back += 1;
        throw new Error("Some error while executing");
    });
    blueslip.expect(
        "error",
        `Error while executing callback 'Anonymous function' from unsuspend_callbacks.`,
    );
    watchdog.check_for_unsuspend();
    assert.equal(num_times_called_back, 2);
});

run_test("suspect_offline", () => {
    const watchdog = zrequire("watchdog");
    watchdog._reset_for_testing();
    watchdog.initialize();
    watchdog.set_suspect_offline(true);
    assert.ok(watchdog.suspects_user_is_offline());

    watchdog.set_suspect_offline(false);
    assert.ok(!watchdog.suspects_user_is_offline());
});

run_test("browser_events", () => {
    const watchdog = zrequire("watchdog");
    watchdog._reset_for_testing();
    watchdog.initialize();
    // Verify handlers were registered
    assert.ok(resume_handler);
    assert.ok(pageshow_handler);

    let num_times_called_back = 0;
    watchdog.on_unsuspend(() => {
        num_times_called_back += 1;
    });

    // Simulate resume event (after >75s delay)
    advance_secs(80);
    resume_handler();
    assert.equal(num_times_called_back, 1);

    // Simulate pageshow event (persisted) (after >75s delay)
    advance_secs(80);
    pageshow_handler({persisted: true});
    assert.equal(num_times_called_back, 2);

    // Simulate pageshow event (not persisted)
    advance_secs(80);
    pageshow_handler({persisted: false});
    assert.equal(num_times_called_back, 2);
});

run_test("reset MockDate", () => {
    MockDate.reset();
});
