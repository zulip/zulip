"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const {current_user} = require("./lib/zpage_params");

const channel = mock_esm("../src/channel");
const reload = mock_esm("../src/reload");
const reload_state = mock_esm("../src/reload_state");
const sent_messages = mock_esm("../src/sent_messages", {
    start_tracking_message: noop,
    get_message_state: () => ({
        report_server_ack: noop,
        saw_event: true,
    }),
    start_send: noop,
});
const server_events = mock_esm("../src/server_events");

const people = zrequire("people");
const transmit = zrequire("transmit");
const stream_data = zrequire("stream_data");

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

    assert.ok(success_func_called);

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
    assert.ok(error_func_called);
});

run_test("transmit_message_ajax_reload_pending", () => {
    /* istanbul ignore next */
    const success = () => {
        throw new Error("unexpected success");
    };
    /* istanbul ignore next */
    const error = () => {
        throw new Error("unexpected error");
    };

    reload_state.is_pending = () => true;

    let reload_initiated;
    reload.initiate = (opts) => {
        reload_initiated = true;
        assert.deepEqual(opts, {
            immediate: true,
            save_compose: true,
            send_after_reload: true,
        });
    };

    const request = {foo: "bar"};

    channel.post = (opts) => {
        assert.equal(opts.url, "/json/messages");
        assert.equal(opts.data.foo, "bar");
        const xhr = "whatever";
        opts.error(xhr, "bad request");
    };
    transmit.send_message(request, success, error);
    assert.ok(reload_initiated);
});

run_test("topic wildcard mention not allowed", ({override}) => {
    /* istanbul ignore next */
    const success = () => {
        throw new Error("unexpected success");
    };

    /* istanbul ignore next */
    const error = (_response, server_error_code) => {
        assert.equal(server_error_code, "TOPIC_WILDCARD_MENTION_NOT_ALLOWED");
    };

    override(reload_state, "is_pending", () => false);

    const request = {foo: "bar"};
    override(channel, "post", (opts) => {
        assert.equal(opts.url, "/json/messages");
        assert.equal(opts.data.foo, "bar");
        const xhr = {
            responseJSON: {
                code: "TOPIC_WILDCARD_MENTION_NOT_ALLOWED",
            },
        };
        opts.error(xhr, "bad request");
    });

    transmit.send_message(request, success, error);
});

run_test("reply_message_stream", ({override}) => {
    const social_stream_id = 555;
    stream_data.add_sub({
        name: "social",
        stream_id: social_stream_id,
    });

    const stream_message = {
        type: "stream",
        stream_id: social_stream_id,
        topic: "lunch",
        sender_full_name: "Alice",
        sender_id: 123,
    };

    const content = "hello";

    let send_message_args;

    override(channel, "post", ({data}) => {
        send_message_args = data;
    });

    current_user.user_id = 44;
    server_events.queue_id = 66;
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

run_test("reply_message_private", ({override}) => {
    const fred = {
        user_id: 3,
        email: "fred@example.com",
        full_name: "Fred Frost",
    };
    people.add_active_user(fred);

    const pm_message = {
        type: "private",
        display_recipient: [{id: fred.user_id}],
    };

    const content = "hello";

    let send_message_args;

    override(channel, "post", ({data}) => {
        send_message_args = data;
    });

    current_user.user_id = 155;
    server_events.queue_id = 177;
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

    blueslip.expect("error", "unknown message type");

    transmit.reply_message({
        message: bogus_message,
    });
});
