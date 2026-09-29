"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const server_time = zrequire("server_time");

run_test("no offset before the server reports its time", () => {
    assert.ok(Math.abs(server_time.now() - Date.now() / 1000) < 1);
});

run_test("client clock behind the server", () => {
    server_time.update_offset(Date.now() / 1000 + 3600);
    assert.ok(Math.abs(server_time.now() - (Date.now() / 1000 + 3600)) < 1);
});

run_test("client clock ahead of the server", () => {
    server_time.update_offset(Date.now() / 1000 - 3600);
    assert.ok(Math.abs(server_time.now() - (Date.now() / 1000 - 3600)) < 1);
});
