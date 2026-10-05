"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/message_feed_loading", {
    hide_loading_initial_page: noop,
});
set_global("addEventListener", noop);
set_global("setTimeout", noop);

const channel = mock_esm("../src/channel");
mock_esm("../src/reload_state", {
    is_in_progress() {
        return false;
    },
});
page_params.test_suite = false;

// we also directly write to pointer
set_global("pointer", {});

mock_esm("../src/popup_banners", {
    close_connection_error_popup_banner() {},
});

mock_esm("../src/stream_events", {
    update_property() {
        throw new Error("subs update error");
    },
});

mock_esm("../src/sent_messages", {
    report_event_received() {},
    messages: new Map(),
});

const reaction_events = mock_esm("../src/reaction_events", {
    received_reactions() {},
});

const submessage = mock_esm("../src/submessage", {
    handle_event() {},
});

const message_events = mock_esm("../src/message_events", {
    insert_new_messages() {
        throw new Error("insert error");
    },
    update_messages() {
        throw new Error("update error");
    },
});

const server_events = zrequire("server_events");
const server_events_state = zrequire("server_events_state");

const message = {
    id: 1,
    sender_id: 2,
    content: "hello",
    recipient_id: 3,
    timestamp: 100000000,
    client: "website",
    subject: "server_test",
    topic_links: [],
    is_me_message: false,
    reactions: [
        {
            emoji_name: "foo",
            emoji_code: "bar",
            reaction_type: "unicode_emoji",
            user: {
                email: "user1@foo.com",
                id: 1,
                full_name: "aaron",
            },
            user_id: 1,
        },
    ],
    submessages: [],
    sender_full_name: "user1",
    sender_email: "user2@foo.com",
    display_recipient: "test",
    type: "stream",
    stream_id: 1,
    avatar_url: "bar",
    content_type: "text/html",
};

function clear_initial_fetch_state() {
    server_events.clear_for_testing();
    server_events_state.clear_for_testing();
}

run_test("events response during initial fetch is applied when it finishes", ({override}) => {
    clear_initial_fetch_state();
    let get_events_options;
    override(channel, "get", (options) => {
        get_events_options = options;
    });

    // Events received before the initial message fetch finishes are
    // stored, not applied.
    server_events.restart_get_events();
    get_events_options.success({events: []});
    assert.ok(!server_events_state.has_applied_first_events_response());

    server_events.finished_initial_fetch();
    assert.ok(server_events_state.has_applied_first_events_response());
});

run_test("events response after initial fetch is applied immediately", ({override}) => {
    clear_initial_fetch_state();
    let get_events_options;
    override(channel, "get", (options) => {
        get_events_options = options;
    });

    // Finishing the initial message fetch does not count as an
    // events response.
    server_events.finished_initial_fetch();
    assert.ok(!server_events_state.has_applied_first_events_response());

    server_events.restart_get_events();
    get_events_options.success({events: []});
    assert.ok(server_events_state.has_applied_first_events_response());
});

run_test("message_event", ({override}) => {
    const event = {
        type: "message",
        message,
        flags: [],
    };

    let inserted;
    override(message_events, "insert_new_messages", (message_data) => {
        const messages = message_data.raw_messages;
        assert.equal(messages[0].content, event.message.content);
        inserted = true;
        return messages;
    });

    server_events._get_events_success([event]);
    assert.ok(inserted);
});

run_test("reactions are processed as a batch after the batch's new messages", ({override}) => {
    // A reaction can reach us in the same batch as the message it is on;
    // it would be lost if it were applied before that message is in
    // message_store.
    const reaction_add = {
        type: "reaction",
        op: "add",
        message_id: message.id,
        message_sender_id: message.sender_id,
        user_id: 7,
        reaction_type: "unicode_emoji",
        emoji_name: "tada",
        emoji_code: "1f389",
    };
    const reaction_remove = {...reaction_add, op: "remove"};
    const calls = [];
    override(message_events, "insert_new_messages", () => {
        calls.push("insert_new_messages");
    });
    override(reaction_events, "received_reactions", (events) => {
        calls.push(events);
    });

    server_events._get_events_success([
        reaction_add,
        {type: "message", message, flags: []},
        reaction_remove,
    ]);
    assert.deepEqual(calls, ["insert_new_messages", [reaction_add, reaction_remove]]);
});

// Start blueslip tests here

const setup = () => {
    server_events.finished_initial_fetch();
};

run_test("event_dispatch_error", () => {
    setup();

    const data = {events: [{type: "stream", op: "update", id: 1, other: "thing"}]};
    channel.get = (options) => {
        options.success(data);
    };

    blueslip.expect("error", "Failed to process an event");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info.event.type, "stream");
    assert.equal(logs[0].more_info.event.op, "update");
    assert.equal(logs[0].more_info.event.id, 1);
    assert.equal(logs[0].more_info.other, undefined);
});

run_test("event_new_message_error", () => {
    setup();

    const data = {events: [{type: "message", id: 1, other: "thing", message}]};
    channel.get = (options) => {
        options.success(data);
    };

    blueslip.expect("error", "Failed to insert new messages");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});

run_test("event_edit_message_error", () => {
    setup();
    const data = {events: [{type: "update_message", id: 1, other: "thing"}]};
    channel.get = (options) => {
        options.success(data);
    };
    blueslip.expect("error", "Failed to update messages");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});

run_test("event_reaction_error", ({override}) => {
    setup();
    // A failure to process reactions does not stop the events processed
    // after them.
    const data = {
        events: [
            {type: "reaction", op: "add", id: 1, message_id: message.id},
            {type: "submessage", id: 2, message_id: message.id},
        ],
    };
    channel.get = (options) => {
        options.success(data);
    };
    override(reaction_events, "received_reactions", () => {
        throw new Error("reaction error");
    });
    let handled_submessage = false;
    override(submessage, "handle_event", () => {
        handled_submessage = true;
    });
    blueslip.expect("error", "Failed to process reactions");

    server_events.restart_get_events();

    assert.ok(handled_submessage);
    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});
