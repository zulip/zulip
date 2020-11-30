"use strict";

const {strict: assert} = require("assert");

const {set_global, stub_out_jquery, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const noop = function () {};

set_global("document", {});
set_global("addEventListener", noop);
stub_out_jquery();

zrequire("message_store");
zrequire("server_events_dispatch");
zrequire("server_events");
zrequire("sent_messages");

set_global("channel", {});
set_global("home_msg_list", {
    select_id: noop,
    selected_id() {
        return 1;
    },
});
set_global("page_params", {test_suite: false});
set_global("reload_state", {
    is_in_progress() {
        return false;
    },
});

// we also directly write to pointer
set_global("pointer", {});

set_global("echo", {
    process_from_server(messages) {
        return messages;
    },
    update_realm_filter_rules: noop,
});
set_global("ui_report", {
    hide_error() {
        return false;
    },
    show_error() {
        return false;
    },
});

server_events.home_view_loaded();

run_test("message_event", () => {
    const event = {
        type: "message",
        message: {
            content: "hello",
        },
        flags: [],
    };

    let inserted;
    set_global("message_events", {
        insert_new_messages(messages) {
            assert.equal(messages[0].content, event.message.content);
            inserted = true;
        },
    });

    server_events._get_events_success([event]);
    assert(inserted);
});

// Start blueslip tests here

const setup = function () {
    server_events.home_view_loaded();
    set_global("message_events", {
        insert_new_messages() {
            throw new Error("insert error");
        },
        update_messages() {
            throw new Error("update error");
        },
    });
    set_global("stream_events", {
        update_property() {
            throw new Error("subs update error");
        },
    });
};

run_test("event_dispatch_error", () => {
    setup();

    const data = {events: [{type: "stream", op: "update", id: 1, other: "thing"}]};
    channel.get = function (options) {
        options.success(data);
    };

    blueslip.expect("error", "Failed to process an event\nsubs update error");

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

    const data = {events: [{type: "message", id: 1, other: "thing", message: {}}]};
    channel.get = function (options) {
        options.success(data);
    };

    blueslip.expect("error", "Failed to insert new messages\ninsert error");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});

run_test("event_edit_message_error", () => {
    setup();
    const data = {events: [{type: "update_message", id: 1, other: "thing"}]};
    channel.get = function (options) {
        options.success(data);
    };
    blueslip.expect("error", "Failed to update messages\nupdate error");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});
