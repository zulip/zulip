"use strict";

const {strict: assert} = require("assert");

const MockDate = require("mockdate");

const {set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

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

const watchdog = zrequire("watchdog");

run_test("basics", () => {
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
    advance_secs(21);
    checker();
    assert.equal(num_times_called_back, 1);

    // Simulate healthy operations resume, and
    // explicitly call check_for_unsuspend.
    num_times_called_back = 0;
    advance_secs(5);
    watchdog.check_for_unsuspend();
    assert.equal(num_times_called_back, 0);

    // Simulate another suspension.
    advance_secs(21);
    watchdog.check_for_unsuspend();
    assert.equal(num_times_called_back, 1);
});

run_test("suspect_offline", () => {
    watchdog.set_suspect_offline(true);
    assert.ok(watchdog.suspects_user_is_offline());

    watchdog.set_suspect_offline(false);
    assert.ok(!watchdog.suspects_user_is_offline());
});

run_test("reset MockDate", () => {
    MockDate.reset();
});
