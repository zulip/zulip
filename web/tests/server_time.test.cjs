"use strict";

const assert = require("node:assert/strict");

const {clock, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// performance.now() counts from when the page started loading.
// Setting the system clock doesn't change it, but it can pause while
// the device sleeps, so the tests move it separately from Date.now().
let monotonic_ms = 0;
set_global("performance", {now: () => monotonic_ms});

const server_time = zrequire("server_time");

function tick(ms) {
    clock.tick(ms);
    monotonic_ms += ms;
}

function test(label, f) {
    run_test(label, (helpers) => {
        monotonic_ms = 0;
        server_time.clear_for_testing();
        f(helpers);
    });
}

test("client clock is used until the server reports its time", () => {
    clock.setSystemTime(1000 * 1000);
    assert.equal(server_time.now(), 1000);
});

test("client clock that agrees with the server is left alone", () => {
    clock.setSystemTime(1000 * 1000);
    const request_start = server_time.get_request_start();
    tick(8000);
    // The server read its clock early in this slow request; using the
    // request's midpoint instead would put us 3.75 seconds behind.
    server_time.update_offset(1000.25, request_start);
    assert.equal(server_time.now(), 1008);
});

test("client clock that's ahead is corrected", () => {
    // The client's clock is an hour ahead of the server's.
    clock.setSystemTime(4600 * 1000);
    let request_start = server_time.get_request_start();
    tick(500);
    server_time.update_offset(1000.25, request_start);
    // We don't know when during the request the server read its
    // clock, so we assume the midpoint.
    assert.equal(server_time.now(), 1000.5);

    // A later sample consistent with our estimate doesn't move it.
    tick(59_500);
    request_start = server_time.get_request_start();
    tick(250);
    server_time.update_offset(1060.0625, request_start);
    assert.equal(server_time.now(), 1060.25);

    // The user sets the client's clock even further ahead; the next
    // sample corrects for that.
    clock.setSystemTime(8000 * 1000);
    request_start = server_time.get_request_start();
    tick(500);
    server_time.update_offset(1060.5, request_start);
    assert.equal(server_time.now(), 1060.75);
});

test("client clock that's behind is corrected", () => {
    clock.setSystemTime(1000 * 1000);
    const request_start = server_time.get_request_start();
    tick(500);
    server_time.update_offset(4600.25, request_start);
    assert.equal(server_time.now(), 4600.5);
});

test("device sleeping during a request", () => {
    clock.setSystemTime(1000 * 1000);
    const request_start = server_time.get_request_start();
    // The server answers right away, but the device sleeps for an
    // hour before handling the response, during which
    // performance.now() doesn't advance.
    clock.setSystemTime((1000 + 3600) * 1000);
    tick(250);
    server_time.update_offset(1000.125, request_start);
    assert.equal(server_time.now(), 4600.25);
});

test("client clock set back during a request", () => {
    clock.setSystemTime(10_000 * 1000);
    const request_start = server_time.get_request_start();
    tick(250);
    clock.setSystemTime((10_000.25 - 3600) * 1000);
    tick(250);
    // performance.now() still measures the request as taking 0.5s.
    server_time.update_offset(10_000.25, request_start);
    assert.equal(server_time.now(), 10_000.5);
});

test("initialize bounds the reading by the page's load time", () => {
    // The client's clock is an hour ahead, and the page took 2
    // seconds to load, with the server reading its clock for the
    // initial state data 1 second in.
    clock.setSystemTime(4600 * 1000);
    tick(2000);
    server_time.initialize(1001);
    assert.equal(server_time.now(), 1002);

    // With a correct client clock, initialize changes nothing.
    server_time.clear_for_testing();
    server_time.initialize(4601);
    assert.equal(server_time.now(), 4602);
});
