"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

set_global("document", {hasFocus: () => true});

const channel = mock_esm("../src/channel");
const desktop_notifications = mock_esm("../src/desktop_notifications");
const message_lists = mock_esm("../src/message_lists");
const recent_view_ui = mock_esm("../src/recent_view_ui");
const unread_ui = mock_esm("../src/unread_ui");
const watchdog = mock_esm("../src/watchdog");

message_lists.current = {view: {}, data: {}};
message_lists.all_rendered_message_lists = () => [message_lists.current];

const message_store = zrequire("message_store");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const unread = zrequire("unread");
const unread_ops = zrequire("unread_ops");

const me = {
    email: "me@example.com",
    user_id: 101,
    full_name: "Me Myself",
};

people.init();
people.add_active_user(me);
people.initialize_current_user(me.user_id);

const denmark = make_stream({
    color: "blue",
    name: "Denmark",
    stream_id: 1,
    subscribed: true,
});
stream_data.add_sub_for_tests(denmark);

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

// Helper to set up message_lists.current for mark_as_unread_from_here
// such that do_mark_unread_by_ids is selected (not do_mark_unread_by_narrow).
function setup_message_list_for_mark_unread(override, messages) {
    override(message_lists.current, "all_messages", () => messages);
    override(message_lists.current, "prevent_reading", noop);
    // process_unread_messages_event checks can_mark_messages_read;
    // returning false triggers notify_messages_remain_unread.
    override(message_lists.current, "can_mark_messages_read", () => false);
    override(message_lists.current, "has_unread_messages", () => true);
    message_lists.current.data = {
        filter: {
            get_stringified_narrow_for_server_query: () => "[]",
            may_contain_multiple_conversations: () => false,
        },
        fetch_status: {
            has_found_newest: () => true,
        },
    };
}

run_test("do_mark_unread_by_ids - local echo for stream messages", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const msg1 = {
        id: 50,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
    };
    const msg2 = {
        id: 51,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
    };
    message_store.update_message_cache({type: "server_message", message: msg1});
    message_store.update_message_cache({type: "server_message", message: msg2});

    setup_message_list_for_mark_unread(override, [msg1, msg2]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(watchdog, "suspects_user_is_offline", () => false);
    override(recent_view_ui, "complete_rerender", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(unread_ui, "notify_messages_remain_unread", noop);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(50);

    // Verify server request was sent.
    assert.equal(channel_post_opts.url, "/json/messages/flags");
    assert.deepEqual(JSON.parse(channel_post_opts.data.messages), [50, 51]);
    assert.equal(channel_post_opts.data.op, "remove");
    assert.equal(channel_post_opts.data.flag, "read");

    // Verify local echo: messages should be marked unread
    // before the server responds.
    assert.equal(message_store.get(50).unread, true);
    assert.equal(message_store.get(51).unread, true);

    // Verify the unread module now tracks these as unread.
    assert.deepEqual(unread.get_unread_message_ids([50, 51]), [50, 51]);

    // Simulate successful server response.
    channel_post_opts.success({ignored_because_not_subscribed_channels: []});
});

run_test("do_mark_unread_by_ids - idempotent when server event arrives", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const msg = {
        id: 60,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
    };
    message_store.update_message_cache({type: "server_message", message: msg});

    setup_message_list_for_mark_unread(override, [msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(watchdog, "suspects_user_is_offline", () => false);
    override(recent_view_ui, "complete_rerender", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(unread_ui, "notify_messages_remain_unread", noop);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(60);

    // Local echo applied: message is unread.
    assert.equal(message_store.get(60).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([60]), [60]);

    // Simulate the real server event arriving. Since the message is
    // already unread, get_read_message_ids returns empty, confirming
    // the operation is idempotent.
    assert.deepEqual(unread.get_read_message_ids([60]), []);

    channel_post_opts.success({ignored_because_not_subscribed_channels: []});
});

run_test("do_mark_unread_by_ids - rollback on server error", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const msg = {
        id: 70,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
    };
    message_store.update_message_cache({type: "server_message", message: msg});

    setup_message_list_for_mark_unread(override, [msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(message_lists.current.view, "show_message_as_read", noop);
    override(watchdog, "suspects_user_is_offline", () => false);
    override(recent_view_ui, "complete_rerender", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(unread_ui, "notify_messages_remain_unread", noop);
    override(desktop_notifications, "close_notification", noop);
    override(recent_view_ui, "update_topic_unread_count", noop);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(70);

    // Local echo applied.
    assert.equal(message_store.get(70).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([70]), [70]);

    // Simulate a non-retryable server error (500).
    blueslip.expect("error", "Unexpected error marking messages as unread");
    channel_post_opts.error({
        readyState: 4,
        status: 500,
        responseText: "Internal Server Error",
        responseJSON: {},
    });

    // Local echo should be rolled back: message is read again.
    assert.equal(message_store.get(70).unread, false);
    assert.deepEqual(unread.get_unread_message_ids([70]), []);
});

run_test("do_mark_unread_by_ids - no rollback when offline", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const msg = {
        id: 80,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
    };
    message_store.update_message_cache({type: "server_message", message: msg});

    setup_message_list_for_mark_unread(override, [msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(watchdog, "suspects_user_is_offline", () => false);
    override(recent_view_ui, "complete_rerender", noop);
    override(unread_ui, "update_unread_counts", noop);
    override(unread_ui, "notify_messages_remain_unread", noop);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(80);

    // Local echo applied.
    assert.equal(message_store.get(80).unread, true);

    // Simulate offline error (readyState === 0).
    let online_callback;
    window.addEventListener = (event, callback, options) => {
        assert.equal(event, "online");
        assert.deepEqual(options, {once: true});
        online_callback = callback;
    };
    channel_post_opts.error({readyState: 0});

    // Local echo should be kept in place (not rolled back).
    assert.equal(message_store.get(80).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([80]), [80]);

    // Verify that the retry is registered and fires on reconnect.
    assert.ok(online_callback);
    online_callback();
    assert.ok(channel_post_opts);
});
