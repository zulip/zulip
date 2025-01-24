"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/loading", {
    destroy_indicator: noop,
});
set_global("addEventListener", noop);

const channel = mock_esm("../src/channel");
mock_esm("../src/reload_state", {
    is_in_progress() {
        return false;
    },
    set_csrf_failed_handler() {},
});
page_params.test_suite = false;

// we also directly write to pointer
set_global("pointer", {});

mock_esm("../src/ui_report", {
    hide_error() {
        return false;
    },
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

const message_events = mock_esm("../src/message_events", {
    insert_new_messages() {
        throw new Error("insert error");
    },
    update_messages() {
        throw new Error("update error");
    },
});

const server_events = zrequire("server_events");

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
    sender_realm_str: "foo",
    display_recipient: "test",
    type: "stream",
    stream_id: 1,
    avatar_url: "bar",
    content_type: "text/html",
};

run_test("initialize", ({override}) => {
    override(channel, "get", ({success}) => {
        success({events: []});
    });

    server_events.initialize({
        queue_id: "q",
        server_generation: 1,
        event_queue_longpoll_timeout_seconds: 90,
        last_event_id: -1,
    });

    server_events.finished_initial_fetch();
});

run_test("message_event", ({override}) => {
    const event = {
        id: 1,
        type: "message",
        message,
        flags: [],
    };
    override(channel, "get", ({success}) => {
        success({events: [event]});
    });

    let inserted;
    override(message_events, "insert_new_messages", (messages) => {
        assert.equal(messages[0].content, event.message.content);
        inserted = true;
        return messages;
    });

    server_events.restart_get_events();
    assert.ok(inserted);
});

// Start blueslip tests here

const setup = () => {
    server_events.finished_initial_fetch();
};

run_test("event_dispatch_error", () => {
    setup();

    const data = {
        events: [
            {
                type: "stream",
                op: "update",
                id: 1,
                other: "thing",
                property: "description",
                value: "",
                name: "general",
                stream_id: 1,
            },
        ],
    };
    channel.get = (options) => {
        options.success(data);
    };

    blueslip.expect("error", "Failed to process an event");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].cause.message, "subs update error");
    assert.equal(logs[0].more_info.event.type, "stream");
    assert.equal(logs[0].more_info.event.op, "update");
    assert.equal(logs[0].more_info.event.id, 1);
    assert.equal(logs[0].more_info.other, undefined);
});

run_test("event_new_message_error", () => {
    setup();

    const data = {events: [{type: "message", id: 1, other: "thing", message, flags: []}]};
    channel.get = (options) => {
        options.success(data);
    };

    blueslip.expect("error", "Failed to insert new messages");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].cause.message, "insert error");
    assert.equal(logs[0].more_info, undefined);
});

run_test("event_edit_message_error", () => {
    setup();
    const data = {
        events: [
            {
                type: "update_message",
                id: 1,
                other: "thing",
                user_id: 1,
                rendering_only: false,
                message_id: 1,
                message_ids: [1],
                flags: [],
                edit_timestamp: 1,
            },
        ],
    };
    channel.get = (options) => {
        options.success(data);
    };
    blueslip.expect("error", "Failed to update messages");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].cause.message, "update error");
    assert.equal(logs[0].more_info, undefined);
});
