"use strict";

const {strict: assert} = require("assert");

const {with_overrides, zrequire} = require("../zjsunit/namespace");
const {make_stub} = require("../zjsunit/stub");
const {run_test} = require("../zjsunit/test");
const {page_params, user_settings} = require("../zjsunit/zpage_params");

const message_store = zrequire("message_store");
const starred_messages = zrequire("starred_messages");
const stream_popover = zrequire("stream_popover");
const top_left_corner = zrequire("top_left_corner");

run_test("add starred", ({override}) => {
    starred_messages.starred_ids.clear();
    assert.deepEqual(starred_messages.get_starred_msg_ids(), []);
    assert.equal(starred_messages.get_count(), 0);

    override(starred_messages, "rerender_ui", () => {});
    starred_messages.add([1, 2]);
    assert.deepEqual(starred_messages.get_starred_msg_ids(), [1, 2]);
    assert.equal(starred_messages.get_count(), 2);
});

run_test("remove starred", ({override}) => {
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

run_test("initialize", ({override}) => {
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

    user_settings.starred_message_counts = true;
    with_overrides((override) => {
        const stub = make_stub();
        override(stream_popover, "hide_topic_popover", () => {});
        override(top_left_corner, "update_starred_count", stub.f);
        starred_messages.rerender_ui();
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("count");
        assert.equal(args.count, 3);
    });

    user_settings.starred_message_counts = false;
    with_overrides((override) => {
        const stub = make_stub();
        override(stream_popover, "hide_topic_popover", () => {});
        override(top_left_corner, "update_starred_count", stub.f);
        starred_messages.rerender_ui();
        assert.equal(stub.num_calls, 1);
        const args = stub.get_args("count");
        assert.equal(args.count, 0);
    });
});
