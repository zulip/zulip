"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const {page_params} = require("../zjsunit/zpage_params");

const noop = () => {};

set_global("document", {
    to_$() {
        return {
            trigger() {},
        };
    },
});
set_global("addEventListener", noop);

const channel = mock_esm("../../static/js/channel");
const message_lists = mock_esm("../../static/js/message_lists");
mock_esm("../../static/js/reload_state", {
    is_in_progress() {
        return false;
    },
});
message_lists.home = {
    select_id: noop,
    selected_id() {
        return 1;
    },
};
page_params.test_suite = false;

// we also directly write to pointer
set_global("pointer", {});

mock_esm("../../static/js/ui_report", {
    hide_error() {
        return false;
    },
});

mock_esm("../../static/js/stream_events", {
    update_property() {
        throw new Error("subs update error");
    },
});

const message_events = mock_esm("../../static/js/message_events", {
    insert_new_messages() {
        throw new Error("insert error");
    },
    update_messages() {
        throw new Error("update error");
    },
});

const server_events = zrequire("server_events");

server_events.home_view_loaded();

run_test("message_event", ({override}) => {
    const event = {
        type: "message",
        message: {
            content: "hello",
        },
        flags: [],
    };

    let inserted;
    override(message_events, "insert_new_messages", (messages) => {
        assert.equal(messages[0].content, event.message.content);
        inserted = true;
    });

    server_events._get_events_success([event]);
    assert.ok(inserted);
});

// Start blueslip tests here

const setup = () => {
    server_events.home_view_loaded();
};

run_test("event_dispatch_error", () => {
    setup();

    const data = {events: [{type: "stream", op: "update", id: 1, other: "thing"}]};
    channel.get = (options) => {
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
    channel.get = (options) => {
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
    channel.get = (options) => {
        options.success(data);
    };
    blueslip.expect("error", "Failed to update messages\nupdate error");

    server_events.restart_get_events();

    const logs = blueslip.get_test_logs("error");
    assert.equal(logs.length, 1);
    assert.equal(logs[0].more_info, undefined);
});
