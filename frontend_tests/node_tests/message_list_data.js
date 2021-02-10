"use strict";

const {strict: assert} = require("assert");

const {set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const muting = zrequire("muting");
zrequire("unread");

zrequire("Filter", "js/filter");
zrequire("FetchStatus", "js/fetch_status");
const MessageListData = zrequire("MessageListData", "js/message_list_data");

set_global("page_params", {});

set_global("setTimeout", (f, delay) => {
    assert.equal(delay, 0);
    return f();
});

function make_msg(msg_id) {
    return {
        id: msg_id,
        type: "stream",
        unread: true,
        topic: "whatever",
    };
}

function make_msgs(msg_ids) {
    return msg_ids.map((msg_id) => make_msg(msg_id));
}

function assert_contents(mld, msg_ids) {
    const msgs = mld.all_messages();
    assert.deepEqual(msgs, make_msgs(msg_ids));
}

function assert_msg_ids(messages, msg_ids) {
    assert.deepEqual(
        msg_ids,
        messages.map((message) => message.id),
    );
}

run_test("basics", () => {
    const mld = new MessageListData({
        excludes_muted_topics: false,
        filter: undefined,
    });

    assert.equal(mld.is_search(), false);
    assert(mld.can_mark_messages_read());
    mld.add_anywhere(make_msgs([35, 25, 15, 45]));

    assert_contents(mld, [15, 25, 35, 45]);

    const new_msgs = make_msgs([10, 20, 30, 40, 50, 60, 70]);
    const info = mld.add_messages(new_msgs);

    assert.deepEqual(info, {
        top_messages: make_msgs([10]),
        interior_messages: make_msgs([20, 30, 40]),
        bottom_messages: make_msgs([50, 60, 70]),
    });

    assert_contents(mld, [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70]);

    assert.equal(mld.selected_id(), -1);
    assert.equal(mld.closest_id(8), 10);
    assert.equal(mld.closest_id(27), 25);
    assert.equal(mld.closest_id(72), 70);

    mld.set_selected_id(50);
    assert.equal(mld.selected_id(), 50);
    assert.equal(mld.selected_idx(), 8);

    mld.remove([50]);
    assert_contents(mld, [10, 15, 20, 25, 30, 35, 40, 45, 60, 70]);

    mld.update_items_for_muting();
    assert_contents(mld, [10, 15, 20, 25, 30, 35, 40, 45, 60, 70]);

    mld.reset_select_to_closest();
    assert.equal(mld.selected_id(), 45);
    assert.equal(mld.selected_idx(), 7);

    assert.equal(mld.first_unread_message_id(), 10);
    mld.get(10).unread = false;
    assert.equal(mld.first_unread_message_id(), 15);

    mld.clear();
    assert_contents(mld, []);
    assert.equal(mld.closest_id(99), -1);
    assert.equal(mld.get_last_message_sent_by_me(), undefined);

    mld.add_messages(make_msgs([120, 125.01, 130, 140]));
    assert_contents(mld, [120, 125.01, 130, 140]);
    mld.set_selected_id(125.01);
    assert.equal(mld.selected_id(), 125.01);

    mld.get(125.01).id = 145;
    mld.change_message_id(125.01, 145);
    assert_contents(mld, [120, 130, 140, 145]);

    for (const msg of mld.all_messages()) {
        msg.unread = false;
    }

    assert.equal(mld.first_unread_message_id(), 145);
});

run_test("muting", () => {
    let mld = new MessageListData({
        excludes_muted_topics: false,
        filter: undefined,
    });

    const msgs = [
        {id: 1, type: "stream", stream_id: 1, topic: "muted"},
        {id: 2, type: "stream", stream_id: 1, topic: "whatever"},
        {id: 3, type: "stream", stream_id: 1, topic: "muted", mentioned: true}, // mentions override muting
    ];

    // `messages_filtered_for_topic_mutes` should skip filtering
    // messages if `excludes_muted_topics` is false.
    let is_topic_muted_calls = 0;

    with_field(
        muting,
        "is_topic_muted",
        () => {
            is_topic_muted_calls = is_topic_muted_calls + 1;
        },
        () => {
            const res = mld.messages_filtered_for_topic_mutes(msgs);
            assert.equal(is_topic_muted_calls, 0);
            assert.deepEqual(res, msgs);
        },
    );

    // Test actual behaviour of `messages_filtered_for_topic_mutes`
    mld.excludes_muted_topics = true;
    muting.add_muted_topic(1, "muted");
    const res = mld.messages_filtered_for_topic_mutes(msgs);
    assert.deepEqual(res, [
        {id: 2, type: "stream", stream_id: 1, topic: "whatever"},
        {id: 3, type: "stream", stream_id: 1, topic: "muted", mentioned: true}, // mentions override muting
    ]);

    // MessageListData methods should always attempt to filter messages,
    // and update `_all_items` when `excludes_muted_topics` is true.
    mld = new MessageListData({
        excludes_muted_topics: true,
        filter: undefined,
    });
    assert.deepEqual(mld._all_items, []);

    let messages_filtered_for_topic_mutes_calls = 0;
    mld.messages_filtered_for_topic_mutes = function (messages) {
        messages_filtered_for_topic_mutes_calls = messages_filtered_for_topic_mutes_calls + 1;
        return messages;
    };

    mld.add_anywhere([{id: 10}]);
    assert.equal(messages_filtered_for_topic_mutes_calls, 1);
    assert_msg_ids(mld._all_items, [10]);

    mld.prepend([{id: 9}]);
    assert.equal(messages_filtered_for_topic_mutes_calls, 2);
    assert_msg_ids(mld._all_items, [9, 10]);

    mld.append([{id: 11}]);
    assert.equal(messages_filtered_for_topic_mutes_calls, 3);
    assert_msg_ids(mld._all_items, [9, 10, 11]);

    mld.remove([9]);
    assert_msg_ids(mld._all_items, [10, 11]);

    mld.clear();
    assert_msg_ids(mld._all_items, []);

    // Test `add_messages` populates the `info` dict **after**
    // filtering the messages.
    mld = new MessageListData({
        excludes_muted_topics: true,
        filter: undefined,
    });

    const orig_messages = [
        {id: 3, type: "stream", stream_id: 1, topic: "muted"},
        {id: 4, type: "stream", stream_id: 1, topic: "whatever"},
        {id: 7, type: "stream", stream_id: 1, topic: "muted"},
        {id: 8, type: "stream", stream_id: 1, topic: "whatever"},
    ];

    const orig_info = mld.add_messages(orig_messages);
    assert.deepEqual(orig_info, {
        top_messages: [],
        interior_messages: [],
        bottom_messages: [
            {id: 4, type: "stream", stream_id: 1, topic: "whatever"},
            {id: 8, type: "stream", stream_id: 1, topic: "whatever"},
        ],
    });

    assert_msg_ids(mld._all_items, [3, 4, 7, 8]);
    assert_msg_ids(mld._items, [4, 8]);

    const more_messages = [
        {id: 1, type: "stream", stream_id: 1, topic: "muted"},
        {id: 2, type: "stream", stream_id: 1, topic: "whatever"},
        {id: 3, type: "stream", stream_id: 1, topic: "muted"}, // dup
        {id: 5, type: "stream", stream_id: 1, topic: "muted"},
        {id: 6, type: "stream", stream_id: 1, topic: "whatever"},
        {id: 9, type: "stream", stream_id: 1, topic: "muted"},
        {id: 10, type: "stream", stream_id: 1, topic: "whatever"},
    ];

    const more_info = mld.add_messages(more_messages);

    assert_msg_ids(mld._all_items, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    assert_msg_ids(mld._items, [2, 4, 6, 8, 10]);

    assert.deepEqual(more_info, {
        top_messages: [{id: 2, type: "stream", stream_id: 1, topic: "whatever"}],
        interior_messages: [{id: 6, type: "stream", stream_id: 1, topic: "whatever"}],
        bottom_messages: [{id: 10, type: "stream", stream_id: 1, topic: "whatever"}],
    });
});

run_test("errors", () => {
    const mld = new MessageListData({
        excludes_muted_topics: false,
        filter: undefined,
    });
    assert.equal(mld.get("bogus-id"), undefined);

    assert.throws(
        () => {
            mld._add_to_hash(["asdf"]);
        },
        {message: "Bad message id"},
    );

    blueslip.expect("error", "Duplicate message added to MessageListData");
    mld._hash.set(1, "taken");
    mld._add_to_hash(make_msgs([1]));
});
