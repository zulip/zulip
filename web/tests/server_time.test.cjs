"use strict";

const assert = require("node:assert/strict");

const {clock, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const server_time = zrequire("server_time");

run_test("no offset before server reports time", () => {
    server_time._reset_for_testing();
    clock.setSystemTime(1000 * 1000);
    assert.equal(server_time.now(), 1000);
});

run_test("client clock behind server", () => {
    server_time._reset_for_testing();
    clock.setSystemTime(1000 * 1000);
    server_time.update_offset(2000);
    assert.equal(server_time.now(), 2000);

    clock.tick(15 * 1000);
    assert.equal(server_time.now(), 2015);
});

run_test("client clock ahead of server", () => {
    server_time._reset_for_testing();
    clock.setSystemTime(3000 * 1000);
    server_time.update_offset(2000);
    assert.equal(server_time.now(), 2000);

    clock.tick(10 * 1000);
    assert.equal(server_time.now(), 2010);
});

run_test("RTT adjustment", () => {
    server_time._reset_for_testing();
    // Server sampled 2000s mid-flight during a 4s RTT request arriving at t=1004s.
    clock.setSystemTime(1004 * 1000);
    server_time.update_offset(2000, 4);

    // With rtt / 2 compensation, estimated server time at arrival is 2000 + 2 = 2002s.
    assert.equal(server_time.now(), 2002);
});

run_test("reject invalid RTT sample", () => {
    server_time._reset_for_testing();
    clock.setSystemTime(1000 * 1000);
    server_time.update_offset(2000, 0);
    assert.equal(server_time.now(), 2000);

    // Reject samples with rtt > 5s or negative rtt.
    clock.setSystemTime(1010 * 1000);
    server_time.update_offset(5000, 6);
    assert.equal(server_time.now(), 2010);

    server_time.update_offset(5000, -1);
    assert.equal(server_time.now(), 2010);
});
