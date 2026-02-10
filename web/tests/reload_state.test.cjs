"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const reload_state = zrequire("reload_state");

function test(label, f) {
    run_test(label, ({override}) => {
        reload_state.clear_for_testing();
        f({override});
    });
}

test("set_state_to_pending", () => {
    assert.ok(!reload_state.is_pending());
    reload_state.set_state_to_pending();
    assert.ok(reload_state.is_pending());
});

test("set_state_to_in_progress", () => {
    assert.ok(!reload_state.is_in_progress());
    reload_state.set_state_to_in_progress();
    assert.ok(reload_state.is_in_progress());
});
