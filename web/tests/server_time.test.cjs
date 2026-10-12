"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const server_time = zrequire("server_time");
const timerender = zrequire("timerender");

run_test("no offset before server reports time", () => {
    server_time.clear_for_testing();
    const diff = Math.abs(server_time.get_server_time() - Date.now() / 1000);
    assert.ok(diff < 1);
    assert.equal(server_time.get_server_time_offset(), 0);
    assert.equal(server_time.now(), server_time.get_server_time());
    assert.equal(timerender.get_server_time(), server_time.get_server_time());
});

run_test("client clock behind server", () => {
    const future_server_time = Date.now() / 1000 + 3600;
    server_time.update_server_time_offset(future_server_time);
    const diff = Math.abs(server_time.get_server_time() - (Date.now() / 1000 + 3600));
    assert.ok(diff < 1);
    assert.ok(Math.abs(server_time.get_server_time_offset() - 3600) < 1);
    assert.equal(timerender.get_server_time(), server_time.get_server_time());
});

run_test("client clock ahead of server", () => {
    const past_server_time = Date.now() / 1000 - 3600;
    server_time.update_server_time_offset(past_server_time);
    const diff = Math.abs(server_time.get_server_time() - (Date.now() / 1000 - 3600));
    assert.ok(diff < 1);
    assert.ok(Math.abs(server_time.get_server_time_offset() - -3600) < 1);
    assert.equal(timerender.get_server_time(), server_time.get_server_time());
});

run_test("safe handling of invalid server timestamp", () => {
    server_time.clear_for_testing();
    server_time.update_server_time_offset(NaN);
    assert.equal(server_time.get_server_time_offset(), 0);

    server_time.update_server_time_offset(undefined);
    assert.equal(server_time.get_server_time_offset(), 0);
});

run_test("clear_for_testing resets offset", () => {
    server_time.update_server_time_offset(Date.now() / 1000 + 3600);
    assert.notEqual(server_time.get_server_time_offset(), 0);
    server_time.clear_for_testing();
    assert.equal(server_time.get_server_time_offset(), 0);

    server_time.update_server_time_offset(Date.now() / 1000 + 3600);
    timerender.clear_for_testing();
    assert.equal(server_time.get_server_time_offset(), 0);
});
