"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

set_global("document", {hasFocus: () => true});
mock_esm("../src/desktop_notifications", {close_notification: noop});
mock_esm("../src/message_flags", {send_read: noop});
mock_esm("../src/unread_ui", {
    hide_unread_banner: noop,
    update_unread_counts: noop,
});
const recent_view_ui = mock_esm("../src/recent_view_ui");

const message_store = zrequire("message_store");
const unread = zrequire("unread");
const unread_ops = zrequire("unread_ops");

run_test("get_message_count_text", () => {
    unread.set_old_unreads_missing_for_tests(true);
    assert.equal(
        unread_ops.get_message_count_text(5),
        "translated: 5+ messages will be marked as read.",
    );
    assert.equal(
        unread_ops.get_message_count_text(1),
        "translated: 1+ messages will be marked as read.",
    );

    unread.set_old_unreads_missing_for_tests(false);
    assert.equal(
        unread_ops.get_message_count_text(5),
        "translated: 5 messages will be marked as read.",
    );
    assert.equal(
        unread_ops.get_message_count_text(1),
        "translated: 1 message will be marked as read.",
    );
});

function track_unread_stream_message(id, topic) {
    unread.process_unread_message({
        id,
        type: "stream",
        stream_id: 7,
        topic,
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    });
}

run_test("process_read_messages_event", ({override}) => {
    unread.declare_bankruptcy();
    // Only the first message was fetched; the others are known to the
    // unread data alone, as with reads on another client of messages
    // older than what this client has loaded.
    const fetched_message = {id: 101, type: "stream", stream_id: 7, topic: "Lunch", unread: true};
    message_store.set_messages_for_tests([{message: fetched_message}]);
    track_unread_stream_message(101, "Lunch");
    track_unread_stream_message(102, "lunch");
    track_unread_stream_message(103, "dinner");
    unread.process_unread_message({
        id: 104,
        type: "private",
        user_ids_string: "5",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    });

    let updated_conversation_keys;
    override(recent_view_ui, "update_conversations_unread_count", (conversation_keys) => {
        updated_conversation_keys = conversation_keys;
    });

    // Recent view hears about each affected conversation once, whether
    // or not its messages were fetched. Message 105 is not unread.
    unread_ops.process_read_messages_event([101, 102, 103, 104, 105]);
    assert.deepEqual(updated_conversation_keys, new Set(["7:lunch", "7:dinner", "5"]));
    assert.equal(fetched_message.unread, false);
    assert.equal(unread.get_unread_message_count(), 0);

    // Nothing happens for messages that are already read.
    updated_conversation_keys = undefined;
    unread_ops.process_read_messages_event([101, 102]);
    assert.equal(updated_conversation_keys, undefined);
});

run_test("notify_server_messages_read", ({override}) => {
    unread.declare_bankruptcy();
    const messages = [
        {id: 201, type: "stream", stream_id: 7, topic: "Lunch", unread: true},
        {id: 202, type: "stream", stream_id: 7, topic: "lunch", unread: true},
        {id: 203, type: "private", to_user_ids: "5", unread: true},
        {id: 204, type: "stream", stream_id: 7, topic: "already read", unread: false},
    ];
    track_unread_stream_message(201, "Lunch");
    track_unread_stream_message(202, "lunch");
    unread.process_unread_message({
        id: 203,
        type: "private",
        user_ids_string: "5",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    });

    let updated_conversation_keys;
    override(recent_view_ui, "update_conversations_unread_count", (conversation_keys) => {
        updated_conversation_keys = conversation_keys;
    });

    unread_ops.notify_server_messages_read(messages);
    assert.deepEqual(updated_conversation_keys, new Set(["7:lunch", "5"]));
    assert.equal(unread.get_unread_message_count(), 0);
});
