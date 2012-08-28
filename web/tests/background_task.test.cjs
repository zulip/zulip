"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const background_task = zrequire("background_task");

run_test("background task runs", () => {
    let did_run = false;
    let async_did_run = false;
    async function task() {
        did_run = true;
        await Promise.resolve("ok");
        async_did_run = true;
    }

    background_task.run_async_function_without_await(task);
    assert.equal(did_run, true);
    assert.equal(async_did_run, false);
});
