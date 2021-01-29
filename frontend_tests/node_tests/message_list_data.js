"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

zrequire("unread");

zrequire("Filter", "js/filter");
zrequire("FetchStatus", "js/fetch_status");
zrequire("MessageListData", "js/message_list_data");

set_global("page_params", {});
set_global("muting", {});

set_global("setTimeout", (f, delay) => {
    assert.equal(delay, 0);
    return f();
});

function make_msg(msg_id) {
    return {
        id: msg_id,
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

run_test("basics", () => {
    const mld = new MessageListData({
        muting_enabled: false,
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

run_test("muting enabled", () => {
    const mld = new MessageListData({
        muting_enabled: true,
        filter: undefined,
    });

    muting.is_topic_muted = function () {
        return true;
    };
    mld.add_anywhere(make_msgs([35, 25, 15, 45]));
    assert_contents(mld, []);

    mld.get(35).mentioned = true;
    mld.update_items_for_muting();
    assert.deepEqual(mld._items, [mld.get(35)]);

    mld.remove([35, 15]);
    assert_contents(mld, []);
    assert.deepEqual(mld._all_items, make_msgs([25, 45]));

    const msgs = make_msgs([10, 20]);
    msgs[0].mentioned = true;
    mld.prepend(msgs);
    assert.deepEqual(mld._items, [mld.get(10)]);
    assert.deepEqual(mld._all_items, msgs.concat(make_msgs([25, 45])));

    mld.clear();
    assert.deepEqual(mld._all_items, []);
});

run_test("more muting", () => {
    muting.is_topic_muted = function (stream_id, topic) {
        return topic === "muted";
    };

    const mld = new MessageListData({
        muting_enabled: true,
        filter: undefined,
    });

    const orig_messages = [
        {id: 3, topic: "muted"},
        {id: 4, topic: "whatever"},
        {id: 7, topic: "muted"},
        {id: 8, topic: "whatever"},
    ];

    const orig_info = mld.add_messages(orig_messages);

    assert.deepEqual(orig_info, {
        top_messages: [],
        interior_messages: [],
        bottom_messages: [
            {id: 4, topic: "whatever"},
            {id: 8, topic: "whatever"},
        ],
    });

    assert.deepEqual(
        mld._all_items.map((message) => message.id),
        [3, 4, 7, 8],
    );

    assert.deepEqual(
        mld.all_messages().map((message) => message.id),
        [4, 8],
    );

    const more_messages = [
        {id: 1, topic: "muted"},
        {id: 2, topic: "whatever"},
        {id: 3, topic: "muted"}, // dup
        {id: 5, topic: "muted"},
        {id: 6, topic: "whatever"},
        {id: 9, topic: "muted"},
        {id: 10, topic: "whatever"},
    ];

    const more_info = mld.add_messages(more_messages);

    assert.deepEqual(
        mld._all_items.map((message) => message.id),
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    );

    assert.deepEqual(
        mld.all_messages().map((message) => message.id),
        [2, 4, 6, 8, 10],
    );

    assert.deepEqual(more_info, {
        top_messages: [{id: 2, topic: "whatever"}],
        interior_messages: [{id: 6, topic: "whatever"}],
        bottom_messages: [{id: 10, topic: "whatever"}],
    });
});

run_test("errors", () => {
    const mld = new MessageListData({
        muting_enabled: false,
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
