"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const reload_state = zrequire("reload_state");

run_test("set_state_to_pending", () => {
    assert(!reload_state.is_pending());
    reload_state.set_state_to_pending();
    assert(reload_state.is_pending());
});

run_test("set_state_to_in_progress", () => {
    assert(!reload_state.is_in_progress());
    reload_state.set_state_to_in_progress();
    assert(reload_state.is_in_progress());
});
