"use strict";

const {strict: assert} = require("assert");

const {mock_module, set_global, use} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const noop = () => {};

const page_params = set_global("page_params", {});
const channel = mock_module("channel", {});
const reload = mock_module("reload", {});
const reload_state = mock_module("reload_state", {});
const sent_messages = {
    start_tracking_message: noop,
    report_server_ack: noop,
};

mock_module("sent_messages", sent_messages);

const {people, transmit} = use("fold_dict", "people", "transmit");

run_test("transmit_message_ajax", () => {
    let success_func_called;
    const success = () => {
        success_func_called = true;
    };

    const request = {foo: "bar"};

    channel.post = (opts) => {
        assert.equal(opts.url, "/json/messages");
        assert.equal(opts.data.foo, "bar");
        opts.success();
    };

    transmit.send_message(request, success);

    assert(success_func_called);

    channel.xhr_error_message = (msg) => {
        assert.equal(msg, "Error sending message");
        return msg;
    };

    channel.post = (opts) => {
        assert.equal(opts.url, "/json/messages");
        assert.equal(opts.data.foo, "bar");
        const xhr = "whatever";
        opts.error(xhr, "timeout");
    };

    let error_func_called;
    const error = (response) => {
        assert.equal(response, "Error sending message");
        error_func_called = true;
    };
    transmit.send_message(request, success, error);
    assert(error_func_called);
});

run_test("transmit_message_ajax_reload_pending", () => {
    const success = () => {
        throw new Error("unexpected success");
    };

    reload_state.is_pending = () => true;

    let reload_initiated;
    reload.initiate = (opts) => {
        reload_initiated = true;
        assert.deepEqual(opts, {
            immediate: true,
            save_pointer: true,
            save_narrow: true,
            save_compose: true,
            send_after_reload: true,
        });
    };

    const request = {foo: "bar"};

    let error_func_called;
    const error = (response) => {
        assert.equal(response, "Error sending message");
        error_func_called = true;
    };

    error_func_called = false;
    channel.post = (opts) => {
        assert.equal(opts.url, "/json/messages");
        assert.equal(opts.data.foo, "bar");
        const xhr = "whatever";
        opts.error(xhr, "bad request");
    };
    transmit.send_message(request, success, error);
    assert(!error_func_called);
    assert(reload_initiated);
});

run_test("reply_message_stream", () => {
    const stream_message = {
        type: "stream",
        stream: "social",
        topic: "lunch",
        sender_full_name: "Alice",
        sender_id: 123,
    };

    const content = "hello";

    let send_message_args;

    transmit.__Rewire__("send_message", (args) => {
        send_message_args = args;
    });

    page_params.user_id = 44;
    page_params.queue_id = 66;
    sent_messages.get_new_local_id = () => "99";

    transmit.reply_message({
        message: stream_message,
        content,
    });

    assert.deepEqual(send_message_args, {
        sender_id: 44,
        queue_id: 66,
        local_id: "99",
        type: "stream",
        to: "social",
        content: "@**Alice** hello",
        topic: "lunch",
    });
});

run_test("reply_message_private", () => {
    const fred = {
        user_id: 3,
        email: "fred@example.com",
        full_name: "Fred Frost",
    };
    people.add_active_user(fred);

    people.is_my_user_id = () => false;

    const pm_message = {
        type: "private",
        display_recipient: [{id: fred.user_id}],
    };

    const content = "hello";

    let send_message_args;

    transmit.__Rewire__("send_message", (args) => {
        send_message_args = args;
    });

    page_params.user_id = 155;
    page_params.queue_id = 177;
    sent_messages.get_new_local_id = () => "199";

    transmit.reply_message({
        message: pm_message,
        content,
    });

    assert.deepEqual(send_message_args, {
        sender_id: 155,
        queue_id: 177,
        local_id: "199",
        type: "private",
        to: '["fred@example.com"]',
        content: "hello",
    });
});

run_test("reply_message_errors", () => {
    const bogus_message = {
        type: "bogus",
    };

    blueslip.expect("error", "unknown message type: bogus");

    transmit.reply_message({
        message: bogus_message,
    });
});
