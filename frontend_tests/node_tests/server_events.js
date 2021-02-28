"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const noop = () => {};

set_global("document", {
    to_$() {
        return {
            trigger() {},
        };
    },
});
set_global("addEventListener", noop);

const channel = {__esModule: true};
rewiremock("../../static/js/channel").with(channel);
set_global("home_msg_list", {
    select_id: noop,
    selected_id() {
        return 1;
    },
});
set_global("page_params", {test_suite: false});
rewiremock("../../static/js/reload_state").with({
    is_in_progress() {
        return false;
    },
});

// we also directly write to pointer
set_global("pointer", {});

rewiremock("../../static/js/ui_report").with({
    hide_error() {
        return false;
    },
    show_error() {
        return false;
    },
});

// Turn off $.now so we can import server_events.
set_global("$", {
    now() {},
});

rewiremock.enable();

const server_events = zrequire("server_events");

set_global("$", $);

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

const setup = () => {
    server_events.home_view_loaded();
    set_global("message_events", {
        insert_new_messages() {
            throw new Error("insert error");
        },
        update_messages() {
            throw new Error("update error");
        },
    });
    rewiremock("../../static/js/stream_events").with({
        update_property() {
            throw new Error("subs update error");
        },
    });
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
rewiremock.disable();
