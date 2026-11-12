"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const channel = mock_esm("../src/channel");
mock_esm("../src/desktop_notifications", {close_notification: noop});
let send_read_removed_ids = [];
let send_read_in_flight_waiter;
mock_esm("../src/message_flags", {
    send_read: {
        add: noop,
        remove_from_queue(ids) {
            send_read_removed_ids.push(...ids);
        },
        wait_for_in_flight(fn) {
            if (send_read_in_flight_waiter) {
                send_read_in_flight_waiter(fn);
            } else {
                fn();
            }
        },
    },
});
mock_esm("../src/unread_ui", {
    hide_unread_banner: noop,
    update_unread_counts: noop,
    notify_messages_remain_unread: noop,
});
const recent_view_ui = mock_esm("../src/recent_view_ui");
const watchdog = mock_esm("../src/watchdog");
const message_lists = mock_esm("../src/message_lists");
message_lists.current = {
    view: {
        show_message_as_read: noop,
        show_messages_as_unread: noop,
    },
    data: {},
    has_unread_messages: () => false,
    can_mark_messages_read: () => false,
};
message_lists.all_rendered_message_lists = () => [message_lists.current];

const message_store = zrequire("message_store");
const people = zrequire("people");
const {get_topic_key} = zrequire("recent_view_util");
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

const stream_id = 7;
const dm_user_ids_string = "5";

function track_unread_stream_message(id, topic) {
    unread.process_unread_message({
        id,
        type: "stream",
        stream_id,
        topic,
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    });
}

function track_unread_direct_message(id) {
    unread.process_unread_message({
        id,
        type: "private",
        user_ids_string: dm_user_ids_string,
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
    const fetched_message = {id: 101, type: "stream", stream_id, topic: "Lunch", unread: true};
    message_store.set_messages_for_tests([{message: fetched_message}]);
    track_unread_stream_message(101, "Lunch");
    track_unread_stream_message(102, "lunch");
    track_unread_stream_message(103, "dinner");
    track_unread_direct_message(104);

    let rerendered_conversation_keys;
    override(recent_view_ui, "bulk_inplace_rerender", (conversation_keys) => {
        rerendered_conversation_keys = conversation_keys;
    });

    // Recent view rerenders each affected conversation once, whether or
    // not its messages were fetched. Message 105 is not unread.
    unread_ops.process_read_messages_event([101, 102, 103, 104, 105]);
    assert.deepEqual(
        rerendered_conversation_keys,
        new Set([
            get_topic_key(stream_id, "lunch"),
            get_topic_key(stream_id, "dinner"),
            dm_user_ids_string,
        ]),
    );
    assert.equal(fetched_message.unread, false);
    assert.equal(unread.get_unread_message_count(), 0);

    // Nothing happens for messages that are already read.
    rerendered_conversation_keys = undefined;
    unread_ops.process_read_messages_event([101, 102]);
    assert.equal(rerendered_conversation_keys, undefined);

    // A message tracked without a conversation, as a direct message with
    // no recipients would be, leaves recent view alone.
    unread.process_unread_message({
        id: 106,
        type: "private",
        user_ids_string: "",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    });
    unread_ops.process_read_messages_event([106]);
    assert.equal(rerendered_conversation_keys, undefined);
    assert.equal(unread.get_unread_message_count(), 0);
});

run_test("notify_server_messages_read", ({override}) => {
    // Recent view rerenders each conversation once: the first two messages
    // share a topic, and the last one is already read.
    unread.declare_bankruptcy();
    const messages = [
        {id: 201, type: "stream", stream_id, topic: "Lunch", unread: true},
        {id: 202, type: "stream", stream_id, topic: "lunch", unread: true},
        {id: 203, type: "private", to_user_ids: dm_user_ids_string, unread: true},
        {id: 204, type: "stream", stream_id, topic: "already read", unread: false},
    ];
    track_unread_stream_message(201, "Lunch");
    track_unread_stream_message(202, "lunch");
    track_unread_direct_message(203);

    let rerendered_conversation_keys;
    override(recent_view_ui, "bulk_inplace_rerender", (conversation_keys) => {
        rerendered_conversation_keys = conversation_keys;
    });

    unread_ops.notify_server_messages_read(messages);
    assert.deepEqual(
        rerendered_conversation_keys,
        new Set([get_topic_key(stream_id, "lunch"), dm_user_ids_string]),
    );
    assert.equal(unread.get_unread_message_count(), 0);
});

run_test("initialize - update_views_callback", ({override}) => {
    override(window, "to_$", () => ({
        on: noop,
    }));
    override(recent_view_ui, "bulk_inplace_rerender", noop);
    override(recent_view_ui, "complete_rerender", noop);
    const updated_views = [];
    unread_ops.initialize({
        update_views_callback(ids, prop, value) {
            updated_views.push({ids, prop, value});
        },
    });

    unread.declare_bankruptcy();
    const msg = {
        id: 301,
        type: "stream",
        stream_id,
        topic: "copenhagen",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: msg});
    track_unread_stream_message(301, "copenhagen");

    unread_ops.process_read_messages_event([301]);
    assert.deepEqual(updated_views, [{ids: [301], prop: "is-unread", value: false}]);

    updated_views.length = 0;
    unread_ops.process_unread_messages_event({
        message_ids: [301],
        message_details: {
            301: {
                type: "stream",
                stream_id,
                topic: "copenhagen",
                mentioned: false,
                unmuted_stream_msg: true,
            },
        },
    });
    assert.deepEqual(updated_views, [{ids: [301], prop: "is-unread", value: true}]);
    unread_ops.initialize();
});

function setup_message_list_for_mark_unread(override, messages) {
    override(message_lists.current, "all_messages", () => messages);
    override(message_lists.current, "prevent_reading", noop);
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
    send_read_removed_ids = [];

    const msg1 = {
        id: 50,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    const msg2 = {
        id: 51,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: msg1});
    message_store.update_message_cache({type: "server_message", message: msg2});

    setup_message_list_for_mark_unread(override, [msg1, msg2]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(recent_view_ui, "complete_rerender", noop);
    override(watchdog, "suspects_user_is_offline", () => false);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(50);

    // Verify pending read queue was cleared for these messages.
    assert.deepEqual(send_read_removed_ids, [50, 51]);

    // Verify server request was sent.
    assert.equal(channel_post_opts.url, "/json/messages/flags");
    assert.deepEqual(JSON.parse(channel_post_opts.data.messages), [50, 51]);
    assert.equal(channel_post_opts.data.op, "remove");
    assert.equal(channel_post_opts.data.flag, "read");

    // Verify local echo: messages should be marked unread before server responds.
    assert.equal(message_store.get(50).unread, true);
    assert.equal(message_store.get(51).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([50, 51]), [50, 51]);

    // Simulate server success.
    channel_post_opts.success({ignored_because_not_subscribed_channels: []});
    assert.equal(unread_ops.pending_unread_message_ids.has(50), false);
    assert.equal(unread_ops.pending_unread_message_ids.has(51), false);
});

run_test("do_mark_unread_by_ids - local echo for direct messages", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const other_user = {
        email: "other@example.com",
        user_id: 102,
        full_name: "Other User",
    };
    people.add_active_user(other_user);

    const pm_msg = {
        id: 55,
        type: "private",
        display_recipient: [{id: me.user_id}, {id: other_user.user_id}],
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: pm_msg});

    setup_message_list_for_mark_unread(override, [pm_msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(recent_view_ui, "complete_rerender", noop);
    override(watchdog, "suspects_user_is_offline", () => false);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(55);

    assert.equal(message_store.get(55).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([55]), [55]);

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
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: msg});

    setup_message_list_for_mark_unread(override, [msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(recent_view_ui, "complete_rerender", noop);
    override(watchdog, "suspects_user_is_offline", () => false);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(60);

    assert.equal(message_store.get(60).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([60]), [60]);

    // Simulate the real server event arriving. Since the message is
    // already unread, get_read_message_ids returns empty, confirming idempotence.
    assert.deepEqual(unread.get_read_message_ids([60]), []);

    channel_post_opts.success({ignored_because_not_subscribed_channels: []});
});

run_test("do_mark_unread_by_ids - rollback on server error", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const msg_read = {
        id: 70,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    const msg_already_unread = {
        id: 71,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: msg_read});
    message_store.update_message_cache({type: "server_message", message: msg_already_unread});
    unread.process_unread_message({
        id: 71,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: true,
        mentioned: false,
        mentioned_me_directly: false,
    });

    setup_message_list_for_mark_unread(override, [msg_read, msg_already_unread]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(message_lists.current.view, "show_message_as_read", noop);
    override(recent_view_ui, "bulk_inplace_rerender", noop);
    override(recent_view_ui, "complete_rerender", noop);
    override(watchdog, "suspects_user_is_offline", () => false);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(70);

    // Local echo applied to msg_read; msg_already_unread stays unread.
    assert.equal(message_store.get(70).unread, true);
    assert.equal(message_store.get(71).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([70, 71]), [70, 71]);

    // Simulate client error (400).
    blueslip.expect("error", "Unexpected error marking messages as unread");
    channel_post_opts.error({
        readyState: 4,
        status: 400,
        responseText: "Bad Request",
        responseJSON: {},
    });

    // Local echo rolled back for msg_read, while pre-existing unread
    // message stays unread.
    assert.equal(message_store.get(70).unread, false);
    assert.equal(message_store.get(71).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([70, 71]), [71]);
    assert.equal(unread_ops.pending_unread_message_ids.has(70), false);
    assert.equal(unread_ops.pending_unread_message_ids.has(71), false);
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
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: msg});

    setup_message_list_for_mark_unread(override, [msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(recent_view_ui, "complete_rerender", noop);
    override(watchdog, "suspects_user_is_offline", () => false);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    unread_ops.mark_as_unread_from_here(80);

    assert.equal(message_store.get(80).unread, true);

    // Simulate offline error (readyState === 0).
    let online_callback;
    override(window, "addEventListener", (event, callback, options) => {
        assert.equal(event, "online");
        assert.deepEqual(options, {once: true});
        online_callback = callback;
    });
    channel_post_opts.error({readyState: 0});

    // Local echo should be kept in place (not rolled back).
    assert.equal(message_store.get(80).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([80]), [80]);
    assert.equal(unread_ops.pending_unread_message_ids.has(80), true);

    // Verify that the retry is registered and fires on reconnect.
    assert.ok(online_callback);
    channel_post_opts = undefined;
    online_callback();
    assert.ok(channel_post_opts);
    channel_post_opts.success({ignored_because_not_subscribed_channels: []});
});

run_test("do_mark_unread_by_ids - in-flight reconciliation and serialization", ({override}) => {
    message_store.clear_for_testing();
    unread.declare_bankruptcy();

    const msg = {
        id: 90,
        type: "stream",
        stream_id: denmark.stream_id,
        topic: "copenhagen",
        unread: false,
        mentioned: false,
        mentioned_me_directly: false,
        content: "",
    };
    message_store.update_message_cache({type: "server_message", message: msg});

    setup_message_list_for_mark_unread(override, [msg]);
    override(message_lists.current.view, "show_messages_as_unread", noop);
    override(recent_view_ui, "bulk_inplace_rerender", noop);
    override(recent_view_ui, "complete_rerender", noop);
    override(watchdog, "suspects_user_is_offline", () => false);

    let channel_post_opts;
    override(channel, "post", (opts) => {
        channel_post_opts = opts;
    });

    // Test network request serialization: wait_for_in_flight delays post until read completes.
    let in_flight_resume;
    send_read_in_flight_waiter = (resume) => {
        in_flight_resume = resume;
    };

    unread_ops.mark_as_unread_from_here(90);

    // Optimistic local echo took effect immediately before network request was sent.
    assert.equal(message_store.get(90).unread, true);
    assert.equal(channel_post_opts, undefined);
    assert.ok(in_flight_resume);

    // While pending unread, an incoming server read event for message 90 must be dropped!
    unread_ops.process_read_messages_event([90]);
    // Message 90 remains unread!
    assert.equal(message_store.get(90).unread, true);
    assert.deepEqual(unread.get_unread_message_ids([90]), [90]);

    // Now resume in-flight waiter.
    in_flight_resume();
    assert.ok(channel_post_opts);
    send_read_in_flight_waiter = undefined;

    // When user explicitly reads message 90 locally, pending_unread_message_ids is cleared.
    unread_ops.notify_server_messages_read([msg]);
    assert.equal(unread_ops.pending_unread_message_ids.has(90), false);
});

run_test("do_mark_unread_by_ids - empty list does not send request", ({disallow, override}) => {
    disallow(channel, "post");
    override(message_lists.current, "all_messages", () => []);
    override(message_lists.current, "prevent_reading", noop);
    override(watchdog, "suspects_user_is_offline", () => false);
    message_lists.current.data = {
        filter: {
            get_stringified_narrow_for_server_query: () => "[]",
            may_contain_multiple_conversations: () => false,
        },
        fetch_status: {
            has_found_newest: () => true,
        },
    };

    unread_ops.mark_as_unread_from_here(999);
    assert.equal(unread_ops.pending_unread_message_ids.has(999), false);
});
