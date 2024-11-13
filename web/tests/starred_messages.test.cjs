"use strict";

const assert = require("node:assert/strict");

const {mock_esm, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test} = require("./lib/test.cjs");

const left_sidebar_navigation_area = mock_esm("../src/left_sidebar_navigation_area", {
    update_starred_count() {},
});
const message_store = zrequire("message_store");
const starred_messages = zrequire("starred_messages");
const starred_messages_ui = zrequire("starred_messages_ui");
const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

run_test("add starred", () => {
    starred_messages.starred_ids.clear();
    assert.deepEqual(starred_messages.get_starred_msg_ids(), []);
    assert.equal(starred_messages.get_count(), 0);

    starred_messages.add([1, 2]);
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1, 2]);
    assert.equal(starred_messages.get_count(), 2);
});

run_test("remove starred", () => {
    starred_messages.starred_ids.clear();
    assert.deepEqual(starred_messages.get_starred_msg_ids(), []);

    for (const id of [1, 2, 3]) {
        starred_messages.starred_ids.add(id);
    }
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1, 2, 3]);

    starred_messages.remove([2, 3]);
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1]);
    assert.equal(starred_messages.get_count(), 1);
});

run_test("get starred ids in topic", () => {
    for (const id of [1, 2, 3, 4, 5]) {
        starred_messages.starred_ids.add(id);
    }

    assert.deepEqual(starred_messages.get_count_in_topic(undefined, "topic name"), 0);
    assert.deepEqual(starred_messages.get_count_in_topic(3, undefined), 0);

    // id: 1 isn't inserted, to test handling the case
    // when message_store.get() returns undefined
    message_store.update_message_cache({
        id: 2,
        type: "private",
    });
    message_store.update_message_cache({
        // Different stream
        id: 3,
        type: "stream",
        stream_id: 19,
        topic: "topic",
    });
    message_store.update_message_cache({
        // Different topic
        id: 4,
        type: "stream",
        stream_id: 20,
        topic: "some other topic",
    });
    message_store.update_message_cache({
        // Correct match
        id: 5,
        type: "stream",
        stream_id: 20,
        topic: "topic",
    });

    assert.deepEqual(starred_messages.get_count_in_topic(20, "topic"), 1);
});

run_test("initialize", () => {
    starred_messages.starred_ids.clear();
    for (const id of [1, 2, 3]) {
        starred_messages.starred_ids.add(id);
    }

    const starred_messages_params = {
        starred_messages: [4, 5, 6],
    };
    starred_messages.initialize(starred_messages_params);
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [4, 5, 6]);
});

run_test("rerender_ui", ({override}) => {
    starred_messages.starred_ids.clear();
    for (const id of [1, 2, 3]) {
        starred_messages.starred_ids.add(id);
    }

    override(user_settings, "starred_message_counts", true);
    with_overrides(({override}) => {
        const stub = make_stub();
        override(left_sidebar_navigation_area, "update_starred_count", stub.f);
        starred_messages_ui.rerender_ui();
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("count", "hidden");
        assert.equal(args.count, 3);
        assert.equal(args.hidden, false);
    });

    override(user_settings, "starred_message_counts", false);
    with_overrides(({override}) => {
        const stub = make_stub();
        override(left_sidebar_navigation_area, "update_starred_count", stub.f);
        starred_messages_ui.rerender_ui();
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("count", "hidden");
        assert.equal(args.count, 3);
        assert.equal(args.hidden, true);
    });
});
