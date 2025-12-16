"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const channel = mock_esm("../src/channel");
const reload = mock_esm("../src/reload");
const reload_state = mock_esm("../src/reload_state");
const sent_messages = mock_esm("../src/sent_messages", {
    start_tracking_message: noop,
    get_message_state: () => ({
        report_server_ack: noop,
        report_error: noop,
        saw_event: true,
    }),
    wrap_send(_local_id, callback) {
        callback();
    },
});
const server_events_state = mock_esm("../src/server_events_state");

const people = zrequire("people");
const transmit = zrequire("transmit");
const {set_current_user} = zrequire("state_data");
const stream_data = zrequire("stream_data");

const current_user = {};
set_current_user(current_user);

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
    stream_data.add_sub_for_tests({
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

    override(current_user, "user_id", 44);
    server_events_state.queue_id = 66;
    sent_messages.get_new_local_id = () => "99";

    transmit.reply_message(stream_message, content);

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

    override(current_user, "user_id", 155);
    server_events_state.queue_id = 177;
    sent_messages.get_new_local_id = () => "199";

    transmit.reply_message(pm_message, content);

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

    transmit.reply_message(bogus_message, "");
});

run_test("test_idempotency_key", () => {
    reload_state.is_pending = () => false;
    const message_states = {};
    let options;

    // make get_message_state stateful with regards to local_id
    sent_messages.get_message_state = (local_id) => {
        if (local_id === "non-existent") {
            return undefined;
        }
        message_states[local_id] ??= {
            report_server_ack: noop,
            report_error: noop,
            saw_event: true,
        };
        return message_states[local_id];
    };

    channel.post = (opts) => {
        options = opts;
    };

    const request_a = {local_id: "1"};

    // Send a message
    transmit.send_message(request_a, noop, noop);
    const request_a_key = options.idempotencyKeyManager.getKey();

    // Resend the same message
    transmit.send_message(request_a, noop, noop);

    // idempotency key should persist when retrying the successful request for the same message.
    assert.equal(request_a_key, options.idempotencyKeyManager.getKey());

    const request_b = {local_id: "2"};

    // idempotency key should be different for different messages.
    transmit.send_message(request_b, noop, noop);
    assert.notEqual(options.idempotencyKeyManager.getKey(), request_a_key);

    // Resend the first message (request_a) to make sure key was NOT overridden.
    transmit.send_message(request_a, noop, noop);
    assert.equal(options.idempotencyKeyManager.getKey(), request_a_key);

    // No key is generated when get_message_state is undefined.
    transmit.send_message({local_id: "non-existent"}, noop, noop);
    assert.equal(options.idempotencyKeyManager.getKey(), undefined);

    // Error testing

    channel.xhr_error_message = (msg) => msg;

    const request_c = {local_id: "3"};
    transmit.send_message(request_c, noop, noop);
    const request_c_key = options.idempotencyKeyManager.getKey();

    // 5xx error
    channel.post = (opts) => {
        const xhr = {status: 500, responseJSON: {}};
        opts.error(xhr, "some error_type");
    };

    // 5xx error should NOT change key
    transmit.send_message(request_c, noop, noop);
    assert.equal(options.idempotencyKeyManager.getKey(), request_c_key);

    // 4xx error
    channel.post = (opts) => {
        const xhr = {status: 400, responseJSON: {}};
        opts.error(xhr, "some error_type");
    };

    // 4xx error should change key
    transmit.send_message(request_c, noop, noop);
    assert.notEqual(options.idempotencyKeyManager.getKey(), request_c_key);
});
