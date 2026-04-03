"use strict";

const assert = require("node:assert/strict");

const {clock, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const server_time = zrequire("server_time");

run_test("now returns client time when offset is zero", () => {
    server_time.set_clock_offset_seconds(0);
    const client_now = Date.now() / 1000;
    const result = server_time.now();
    assert.ok(Math.abs(result - client_now) < 1);
});

run_test("now adjusts for positive clock offset", () => {
    // Server 1 hour ahead of client.
    clock.setSystemTime(1000000000 * 1000);
    server_time.set_clock_offset_seconds(3600);
    const result = server_time.now();
    assert.ok(Math.abs(result - (1000000000 + 3600)) < 1);
    clock.setSystemTime(0);
    server_time.set_clock_offset_seconds(0);
});

run_test("now adjusts for negative clock offset", () => {
    // Client 1 hour ahead of server.
    clock.setSystemTime(1000000000 * 1000);
    server_time.set_clock_offset_seconds(-3600);
    const result = server_time.now();
    assert.ok(Math.abs(result - (1000000000 - 3600)) < 1);
    clock.setSystemTime(0);
    server_time.set_clock_offset_seconds(0);
});

run_test("update_server_offset computes correct offset", () => {
    // Client at 1000000000, server at 1000003600.
    clock.setSystemTime(1000000000 * 1000);
    server_time.update_server_offset(1000003600);
    assert.ok(Math.abs(server_time.get_clock_offset_seconds() - 3600) < 1);
    clock.setSystemTime(0);
});

run_test("update_server_offset with client ahead of server", () => {
    // Client at 1000003600, server at 1000000000.
    clock.setSystemTime(1000003600 * 1000);
    server_time.update_server_offset(1000000000);
    assert.ok(Math.abs(server_time.get_clock_offset_seconds() - -3600) < 1);

    // now() returns server-relative time.
    const result = server_time.now();
    assert.ok(Math.abs(result - 1000000000) < 1);
    clock.setSystemTime(0);
    server_time.set_clock_offset_seconds(0);
});
