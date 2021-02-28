"use strict";

const {strict: assert} = require("assert");

const {with_overrides, set_global, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");

const page_params = set_global("page_params", {});

zrequire("timerender");
const starred_messages = zrequire("starred_messages");
const top_left_corner = zrequire("top_left_corner");

run_test("add starred", (override) => {
    starred_messages.starred_ids.clear();
    assert.deepEqual(starred_messages.get_starred_msg_ids(), []);
    assert.equal(starred_messages.get_count(), 0);

    override(starred_messages, "rerender_ui", () => {});
    starred_messages.add([1, 2]);
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1, 2]);
    assert.equal(starred_messages.get_count(), 2);
});

run_test("remove starred", (override) => {
    starred_messages.starred_ids.clear();
    assert.deepEqual(starred_messages.get_starred_msg_ids(), []);

    for (const id of [1, 2, 3]) {
        starred_messages.starred_ids.add(id);
    }
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1, 2, 3]);

    override(starred_messages, "rerender_ui", () => {});
    starred_messages.remove([2, 3]);
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1]);
    assert.equal(starred_messages.get_count(), 1);
});

run_test("initialize", (override) => {
    starred_messages.starred_ids.clear();
    for (const id of [1, 2, 3]) {
        starred_messages.starred_ids.add(id);
    }

    page_params.starred_messages = [4, 5, 6];
    override(starred_messages, "rerender_ui", () => {});
    starred_messages.initialize();
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [4, 5, 6]);
});

run_test("rerender_ui", () => {
    starred_messages.starred_ids.clear();
    for (const id of [1, 2, 3]) {
        starred_messages.starred_ids.add(id);
    }

    page_params.starred_message_counts = true;
    with_overrides((override) => {
        const stub = make_stub();
        override(top_left_corner, "update_starred_count", stub.f);
        starred_messages.rerender_ui();
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("count");
        assert.equal(args.count, 3);
    });

    page_params.starred_message_counts = false;
    with_overrides((override) => {
        const stub = make_stub();
        override(top_left_corner, "update_starred_count", stub.f);
        starred_messages.rerender_ui();
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("count");
        assert.equal(args.count, 0);
    });
});
