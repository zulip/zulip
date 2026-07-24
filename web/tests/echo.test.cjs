"use strict";

const assert = require("node:assert/strict");

const {make_user_group} = require("./lib/example_group.cjs");
const {make_stream} = require("./lib/example_stream.cjs");
const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {make_stub} = require("./lib/stub.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const browser_history = mock_esm("../src/browser_history");
const compose_notifications = mock_esm("../src/compose_notifications");
const hash_util = mock_esm("../src/hash_util");
const markdown = mock_esm("../src/markdown");
const message_lists = mock_esm("../src/message_lists");
const message_events_util = mock_esm("../src/message_events_util");
const pm_list = mock_esm("../src/pm_list");
const stream_list = mock_esm("../src/stream_list");

let disparities = [];

mock_esm("../src/message_live_update", {
    update_message_in_all_views() {},
});

mock_esm("../src/sent_messages", {
    mark_disparity(local_id) {
        disparities.push(local_id);
    },
    report_event_received() {},
});

const message_store = mock_esm("../src/message_store", {
    get: () => ({failed_request: true}),

    update_booleans() {},

    maybe_update_raw_content() {},

    update_message_content(message, new_content) {
        message.content = new_content;
    },

    convert_raw_message_to_message_with_booleans() {},
});

message_lists.current = {
    view: {
        rerender_messages: noop,
        change_message_id: noop,
    },
    data: {
        filter: {
            can_apply_locally() {
                return true;
            },
            has_exactly_channel_topic_operators() {
                return true;
            },
            adjust_with_operand_to_message: noop,
            terms: noop,
        },
    },
    change_message_id: noop,
    add_messages: noop,
    remove_and_rerender: noop,
};
const home_msg_list = {
    view: {
        rerender_messages: noop,
        change_message_id: noop,
    },
    data: {
        filter: {
            can_apply_locally() {
                return true;
            },
        },
    },
    preserver_rendered_state: true,
    change_message_id: noop,
    add_messages: noop,
    remove_and_rerender: noop,
};
message_lists.all_rendered_message_lists = () => [home_msg_list, message_lists.current];
message_lists.non_rendered_data = () => [];

const echo = zrequire("echo");
const echo_state = zrequire("echo_state");
const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const {set_current_user} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");

const current_user = {};
set_current_user(current_user);

const general_sub = make_stream({
    stream_id: 101,
    name: "general",
    subscribed: true,
});
stream_data.add_sub_for_tests(general_sub);

run_test("process_from_server for un-echoed messages", () => {
    const waiting_for_ack = new Map();
    const server_messages = [
        {
            local_id: "100.1",
        },
    ];
    echo_state._patch_waiting_for_ack(waiting_for_ack);
    const non_echo_messages = echo.process_from_server(server_messages);
    assert.deepEqual(non_echo_messages, server_messages);
});

run_test("process_from_server for differently rendered messages", ({override}) => {
    let messages_to_rerender = [];

    override(home_msg_list.view, "rerender_messages", (msgs) => {
        messages_to_rerender = msgs;
    });

    // Test that we update all the booleans and the content of the message
    // in local echo.
    const old_value = "old_value";
    const new_value = "new_value";
    const waiting_for_ack = new Map([
        [
            "100.1",
            {
                content: "<p>A client rendered message</p>",
                timestamp: old_value,
                is_me_message: old_value,
                submessages: old_value,
                topic_links: old_value,
            },
        ],
    ]);
    const server_messages = [
        {
            local_id: "100.1",
            content: "<p>A server rendered message</p>",
            timestamp: new_value,
            is_me_message: new_value,
            submessages: new_value,
            topic_links: new_value,
        },
    ];
    echo_state._patch_waiting_for_ack(waiting_for_ack);
    disparities = [];
    const non_echo_messages = echo.process_from_server(server_messages);
    assert.deepEqual(non_echo_messages, []);
    assert.equal(disparities.length, 1);
    assert.deepEqual(messages_to_rerender, [
        {
            content: server_messages[0].content,
            timestamp: new_value,
            is_me_message: new_value,
            submessages: new_value,
            topic_links: new_value,
        },
    ]);
});

run_test("process_from_server for messages to add to narrow", ({override}) => {
    let messages_to_add_to_narrow = [];

    override(message_lists.current.data.filter, "can_apply_locally", () => false);
    override(message_events_util, "maybe_add_narrowed_messages", (msgs, msg_list) => {
        messages_to_add_to_narrow = msgs;
        assert.equal(msg_list, message_lists.current);
    });

    const old_value = "old_value";
    const new_value = "new_value";
    const waiting_for_ack = new Map([
        [
            "100.1",
            {
                content: "<p>rendered message</p>",
                timestamp: old_value,
                is_me_message: old_value,
                submessages: old_value,
                topic_links: old_value,
            },
        ],
    ]);
    const server_messages = [
        {
            local_id: "100.1",
            content: "<p>rendered message</p>",
            timestamp: new_value,
            is_me_message: new_value,
            submessages: new_value,
            topic_links: new_value,
        },
    ];
    echo_state._patch_waiting_for_ack(waiting_for_ack);
    const non_echo_messages = echo.process_from_server(server_messages);
    assert.deepEqual(non_echo_messages, []);
    assert.deepEqual(messages_to_add_to_narrow, [
        {
            content: server_messages[0].content,
            timestamp: new_value,
            is_me_message: new_value,
            submessages: new_value,
            topic_links: new_value,
        },
    ]);
});

run_test("build_display_recipient", ({override}) => {
    override(current_user, "user_id", 123);

    const params = {
        realm_users: [
            {
                user_id: 123,
                full_name: "Iago",
                email: "iago@zulip.com",
            },
            {
                email: "cordelia@zulip.com",
                full_name: "Cordelia",
                user_id: 21,
            },
        ],
    };
    const user_group_params = {
        realm_user_groups: [
            make_user_group({
                is_system_group: true,
                members: [123, 21],
            }),
        ],
    };
    params.realm_non_active_users = [];
    params.cross_realm_bots = [];
    people.initialize(current_user.user_id, params, user_group_params);

    let message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    let display_recipient = echo.build_display_recipient(message);
    assert.equal(display_recipient, "general");

    message = {
        type: "private",
        to_user_ids: "21",
        private_message_recipient: "cordelia@zulip.com",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    display_recipient = echo.build_display_recipient(message);
    assert.equal(display_recipient.length, 2);

    let iago = display_recipient.find((recipient) => recipient.email === "iago@zulip.com");
    assert.equal(iago.full_name, "Iago");
    assert.equal(iago.id, 123);

    const cordelia = display_recipient.find(
        (recipient) => recipient.email === "cordelia@zulip.com",
    );
    assert.equal(cordelia.full_name, "Cordelia");
    assert.equal(cordelia.id, 21);

    message = {
        type: "private",
        to_user_ids: "123",
        private_message_recipient: "iago@zulip.com",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    display_recipient = echo.build_display_recipient(message);

    assert.equal(display_recipient.length, 1);
    iago = display_recipient.find((recipient) => recipient.email === "iago@zulip.com");
    assert.equal(iago.full_name, "Iago");
    assert.equal(iago.id, 123);
});

run_test("update_message_lists", () => {
    home_msg_list.view = {};

    const stub = make_stub();
    const view_stub = make_stub();

    home_msg_list.change_message_id = stub.f;
    home_msg_list.view.change_message_id = view_stub.f;

    echo.update_message_lists({old_id: 401, new_id: 402});

    assert.equal(stub.num_calls, 1);
    const args = stub.get_args("old", "new");
    assert.equal(args.old, 401);
    assert.equal(args.new, 402);

    assert.equal(view_stub.num_calls, 1);
    const view_args = view_stub.get_args("old", "new");
    assert.equal(view_args.old, 401);
    assert.equal(view_args.new, 402);
});

run_test("insert_local_message streams", ({override}) => {
    const fake_now = 555;
    clock.setSystemTime(new Date(fake_now * 1000));

    const local_id_float = 101.01;

    let render_called = false;
    let get_topic_links_called = false;
    let insert_message_called = false;

    override(markdown, "render", () => {
        render_called = true;
    });

    override(markdown, "get_topic_links", () => {
        get_topic_links_called = true;
    });

    const insert_new_messages = (message_data) => {
        const [message] = message_data.raw_messages;
        assert.equal(message.display_recipient, "general");
        assert.equal(message.timestamp, fake_now);
        assert.equal(message.sender_email, "iago@zulip.com");
        assert.equal(message.sender_full_name, "Iago");
        assert.equal(message.sender_id, 123);
        insert_message_called = true;
        return [message];
    };

    const message_request = {
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "important note",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    echo.insert_local_message(message_request, local_id_float, insert_new_messages);

    assert.ok(render_called);
    assert.ok(get_topic_links_called);
    assert.ok(insert_message_called);
});

run_test("insert_local_message direct message", ({override}) => {
    const local_id_float = 102.01;

    override(current_user, "user_id", 123);

    const params = {
        realm_users: [
            {
                user_id: 123,
                full_name: "Iago",
                email: "iago@zulip.com",
            },
            {
                email: "cordelia@zulip.com",
                full_name: "Cordelia",
                user_id: 21,
            },
        ],
    };
    const user_group_params = {
        realm_user_groups: [
            make_user_group({
                is_system_group: true,
                members: [123, 21],
            }),
        ],
    };
    params.realm_non_active_users = [];
    params.cross_realm_bots = [];
    people.init();
    people.initialize(current_user.user_id, params, user_group_params);

    let render_called = false;
    let insert_message_called = false;

    const insert_new_messages = (message_data) => {
        const [message] = message_data.raw_messages;
        assert.equal(message.display_recipient.length, 2);
        insert_message_called = true;
        return [message];
    };

    override(markdown, "render", () => {
        render_called = true;
    });
    override(markdown, "get_topic_links", () => []);

    const message_request = {
        private_message_recipient: "cordelia@zulip.com",
        to_user_ids: "21",
        type: "private",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
    };
    echo.insert_local_message(message_request, local_id_float, insert_new_messages);
    assert.ok(render_called);
    assert.ok(insert_message_called);
});

run_test("edit_locally recomputes content-driven booleans", ({override}) => {
    // A content edit that drops a personal mention should immediately
    // clear the message's mention booleans from the locally rendered
    // flags, rather than leaving them stale until the server event
    // arrives (which would briefly miscolor the message).
    override(markdown, "render", () => ({
        content: "<p>edited, no longer mentions me</p>",
        flags: [],
        is_me_message: false,
    }));
    override(stream_list, "update_streams_sidebar", noop);
    override(pm_list, "update_private_messages", noop);
    override(message_lists, "all_rendered_message_lists", () => [
        {view: {rerender_messages: noop}},
    ]);

    let update_booleans_args;
    override(message_store, "update_booleans", (message, flags) => {
        update_booleans_args = {message, flags};
        message.mentioned = flags.includes("mentioned");
        message.mentioned_me_directly = flags.includes("mentioned");
    });

    const message = {
        id: 42,
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        raw_content: "@**me** original",
        content: "<p>original</p>",
        mentioned: true,
        mentioned_me_directly: true,
    };

    echo.edit_locally(message, {raw_content: "edited, no longer mentions me"});

    assert.equal(update_booleans_args.message, message);
    assert.deepEqual(update_booleans_args.flags, []);
    assert.equal(message.mentioned, false);
    assert.equal(message.mentioned_me_directly, false);
});

run_test("test reify_message_id", ({override}) => {
    const local_id_float = 103.01;

    override(markdown, "render", noop);
    override(markdown, "get_topic_links", noop);
    override(hash_util, "search_terms_to_hash", noop);
    override(browser_history, "update_current_history_state_data", noop);

    const message_request = {
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
        draft_id: 100,
    };
    echo.insert_local_message(message_request, local_id_float, (message_data) => {
        const messages = message_data.raw_messages;
        messages.map((message) => echo.track_local_message(message));
        return messages;
    });

    let message_store_reify_called = false;
    let notifications_reify_called = false;

    override(message_store, "reify_message_id", () => {
        message_store_reify_called = true;
    });

    override(compose_notifications, "reify_message_id", () => {
        notifications_reify_called = true;
    });

    echo.reify_message_id(local_id_float.toString(), 110);

    assert.ok(message_store_reify_called);
    assert.ok(notifications_reify_called);

    const history = stream_topic_history.find_or_create(general_sub.stream_id);
    assert.equal(history.max_message_id, 110);
    assert.equal(history.topics.get("test").message_id, 110);
});

function make_spinner_row() {
    // A stand-in for the failed-message $row. The retry-spinner show/hide
    // helpers look up ".refresh-failed-message" under it and toggle its
    // "rotating" class.
    const $row = $.create("failed-message-row-stub");
    $row.set_find_results(".refresh-failed-message", $.create("refresh-failed-message-stub"));
    return $row;
}

run_test("resend success clears the failed flag", ({override}) => {
    const stored_messages = new Map();
    override(message_store, "get", (id) => stored_messages.get(id));

    const local_id = "300.01";
    const server_id = 310;
    const message = {
        id: Number.parseFloat(local_id),
        local_id,
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        raw_content: "retry me",
        content: "<p>retry me</p>",
        locally_echoed: true,
        failed_request: true,
    };
    // The original send truly failed, so the message is still keyed under its
    // local id, waiting to be retried.
    stored_messages.set(message.id, message);

    const on_send_message_success = (msg, data) => {
        // Mirror the store re-keying that compose.send_message_success ->
        // echo.reify_message_id performs once the server acks the resend.
        stored_messages.delete(msg.id);
        msg.id = data.id;
        msg.locally_echoed = false;
        stored_messages.set(data.id, msg);
    };
    const send_message = (_msg, on_success) => {
        on_success({id: server_id});
    };

    echo.resend_message(message, make_spinner_row(), {on_send_message_success, send_message});

    assert.equal(message.failed_request, false);
    assert.equal(stored_messages.get(server_id), message);
});

run_test("resend error re-marks a present message as failed", ({override}) => {
    // When the resend POST fails while the message is still in the store, the
    // error handler surfaces the failure by setting failed_request back to true.
    const stored_messages = new Map();
    override(message_store, "get", (id) => stored_messages.get(id));

    const message = {
        id: 280,
        local_id: "280.01",
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        raw_content: "retry me",
        content: "<p>retry me</p>",
        locally_echoed: true,
        failed_request: false,
    };
    stored_messages.set(message.id, message);

    const send_message = (_msg, _on_success, on_error) => {
        on_error("error response", "");
    };

    echo.resend_message(message, make_spinner_row(), {on_send_message_success: noop, send_message});

    assert.equal(message.failed_request, true);
});

run_test("resend doesn't crash when the message was already reconciled", ({override}) => {
    // The original send appeared to fail on the client but had actually
    // reached the server. The user resent it; then the original's get-events
    // delivery arrived and reconciled the local echo to the real server id,
    // consuming the local id. By the time the resend's response arrives,
    // reify_message_id early-returns (the local id is gone), so the resent
    // message is never stored under the id the response reports, and
    // failed_message_success must tolerate that missing entry.
    const stored_messages = new Map();
    override(message_store, "get", (id) => stored_messages.get(id));

    const local_id = "250.01";
    const reconciled_id = 260; // server id the message was reconciled to
    // The resend reached the server too and, absent server-side
    // deduplication, created a second message whose id its response reports.
    const resend_response_id = 261;

    // The message has already been reconciled: keyed under its real server id,
    // no longer locally echoed, and no longer failed.
    const message = {
        id: reconciled_id,
        local_id,
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        raw_content: "hello world",
        content: "<p>hello world</p>",
        locally_echoed: false,
        failed_request: false,
    };
    stored_messages.set(reconciled_id, message);

    const on_send_message_success = (msg, data) => {
        // compose.send_message_success calls echo.reify_message_id, which
        // early-returns here because the local id was already consumed.
        echo.reify_message_id(msg.local_id, data.id);
    };
    const send_message = (_msg, on_success) => {
        on_success({id: resend_response_id});
    };

    echo.resend_message(message, make_spinner_row(), {on_send_message_success, send_message});

    // The resend's success path only reconciles the message it resent; it does
    // not store a message under the response's id. (A second message created
    // on the server would instead arrive via its own get-events delivery.) So
    // the store has no entry there, and the reconciled message stays un-failed.
    assert.equal(stored_messages.get(resend_response_id), undefined);
    assert.equal(message.failed_request, false);
});

run_test("resend error on a message removed from the store doesn't crash", ({override}) => {
    // If the resend POST fails after the message was removed from the store
    // (e.g. it was deleted while the resend was in flight), message_send_error
    // must tolerate the missing entry rather than dereference undefined.
    const stored_messages = new Map();
    override(message_store, "get", (id) => stored_messages.get(id));

    const message = {
        id: 270,
        local_id: "270.01",
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        raw_content: "gone",
        content: "<p>gone</p>",
        locally_echoed: true,
        failed_request: false,
    };
    // The message is no longer in the store (stored_messages is empty).

    const send_message = (_msg, _on_success, on_error) => {
        on_error("error response", "");
    };

    // If message_send_error threw on the missing store entry, resend_message
    // would propagate it and fail this test.
    echo.resend_message(message, make_spinner_row(), {
        on_send_message_success: noop,
        send_message,
    });

    // The detached message was left untouched, since there was no stored entry
    // to mark as failed.
    assert.equal(message.failed_request, false);
});

run_test("abort_message clears the failed echo from waiting_for_ack", ({override}) => {
    // Dismissing a failed send must drop its echo from waiting_for_ack, not
    // just from the rendered lists.
    const local_id = "77.01";
    const message = {
        id: 77,
        local_id,
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "test",
        locally_echoed: true,
        failed_request: true,
    };
    echo_state._patch_waiting_for_ack(new Map([[local_id, message]]));
    assert.equal(echo_state.get_message_waiting_for_ack(local_id), message);

    const removed_ids = [];
    override(message_lists.current, "remove_and_rerender", (ids) => {
        removed_ids.push(...ids);
    });

    echo.abort_message(message);

    // Removed from the feed and, crucially, from waiting_for_ack.
    assert.deepEqual(removed_ids, [77]);
    assert.equal(echo_state.get_message_waiting_for_ack(local_id), undefined);
});

run_test("reify_message_id counts a sent direct message", ({override}) => {
    // A sent DM is counted only once acked (on reification), mirroring how
    // stream messages are added to stream_topic_history there.
    const local_id_float = 104.01;

    const iago = {user_id: 123, full_name: "Iago", email: "iago@zulip.com"};
    const cordelia = {user_id: 21, full_name: "Cordelia", email: "cordelia@zulip.com"};
    override(current_user, "user_id", iago.user_id);
    const people_params = {
        realm_users: [iago, cordelia],
        realm_non_active_users: [],
        cross_realm_bots: [],
    };
    const user_group_params = {
        realm_user_groups: [
            make_user_group({is_system_group: true, members: [iago.user_id, cordelia.user_id]}),
        ],
    };
    people.init();
    people.initialize(current_user.user_id, people_params, user_group_params);

    override(markdown, "render", noop);
    override(markdown, "get_topic_links", () => []);
    override(message_store, "reify_message_id", noop);
    override(compose_notifications, "reify_message_id", noop);

    const message_request = {
        private_message_recipient: cordelia.email,
        to_user_ids: cordelia.user_id.toString(),
        type: "private",
        sender_email: iago.email,
        sender_full_name: iago.full_name,
        sender_id: iago.user_id,
    };
    echo.insert_local_message(message_request, local_id_float, (message_data) => {
        const messages = message_data.raw_messages;
        messages.map((message) => echo.track_local_message(message));
        return messages;
    });

    const increment_stub = make_stub();
    override(pm_conversations.recent, "increment_local_message_count", increment_stub.f);

    echo.reify_message_id(local_id_float.toString(), 120);

    assert.equal(increment_stub.num_calls, 1);
    const {user_ids} = increment_stub.get_args("user_ids");
    assert.deepEqual(user_ids, [cordelia.user_id]);
});
