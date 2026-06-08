"use strict";

const assert = require("node:assert/strict");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = zrequire("stream_data");
const message_store = zrequire("message_store");
const message_fetch_raw_content = zrequire("message_fetch_raw_content");
const message_fetch = mock_esm("../src/message_fetch");
const channel = mock_esm("../src/channel");

function add_messages_to_message_store(messages) {
    message_store.clear_for_testing();
    for (const message of messages) {
        message_store.update_message_cache({message});
    }
}

// We only rely on message_fetch for type validation.
message_fetch.message_ids_response_schema = {
    parse: (data) => data,
};

const denmark = {
    subscribed: true,
    color: "blue",
    name: "Denmark",
    stream_id: 1,
};

const social = {
    subscribed: false,
    color: "red",
    name: "social",
    stream_id: 2,
};

const private_shared = {
    subscribed: true,
    invite_only: true,
    history_public_to_subscribers: true,
    color: "green",
    name: "private-shared",
    stream_id: 3,
};

stream_data.add_sub_for_tests(denmark);
stream_data.add_sub_for_tests(social);
stream_data.add_sub_for_tests(private_shared);

function reset_raw_content(message_ids) {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        if (message) {
            delete message.raw_content;
        }
    }
}

run_test("get_raw_content_for_messages", ({override}) => {
    const msg_1 = {
        id: 1,
        raw_content: "Already hydrated content",
        type: "stream",
        stream_id: denmark.stream_id,
        content: "<p>HTML content</p>",
    };
    const msg_2 = {
        id: 2,
        content: "<p>HTML content</p>",
        type: "stream",
        stream_id: denmark.stream_id,
    };
    const msg_3 = {
        id: 3,
        content: "<p>HTML content</p>",
        type: "stream",
        stream_id: social.stream_id,
    };

    add_messages_to_message_store([msg_1, msg_2, msg_3]);

    // Case: All messages already have raw_content
    let success_called = false;
    let error_called = false;
    let success_call_args;

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1],
        on_success() {
            success_called = true;
        },
    });

    assert.ok(success_called, "Should call on_success immediately if all messages are hydrated");
    assert.equal(error_called, false);

    // Case: Fetching missing raw_content successfully
    let channel_get_args;
    success_called = false;
    error_called = false;

    override(channel, "get", (args) => {
        channel_get_args = args;
        args.success({
            messages: [
                {id: 2, content_type: "text/x-markdown", content: "Fetched markdown content"},
            ],
        });
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });

    assert.equal(channel_get_args.url, "/json/messages");
    assert.equal(
        channel_get_args.data.message_ids,
        JSON.stringify([2]),
        "Should only request hydration for messages missing raw_content",
    );
    // It is safe to update raw_content for messages from channels
    // the user is subscribed to.
    assert.equal(msg_2.raw_content, "Fetched markdown content");
    assert.ok(success_called, "Should call on_success after successfully hydrating");
    assert.deepEqual(success_call_args, [msg_1.raw_content, msg_2.raw_content]);

    // Case: Batch endpoint omits a message from an unsubscribed
    // public channel. The channels:public retry should pick it up.
    success_called = false;
    error_called = false;

    let channel_get_call_count = 0;
    override(channel, "get", (args) => {
        channel_get_call_count += 1;
        if (channel_get_call_count === 1) {
            // First batch (no narrow) returns msg_2 but not msg_3.
            assert.equal(args.data.narrow, undefined);
            args.success({
                messages: [
                    {id: 2, content_type: "text/x-markdown", content: "Fetched markdown content"},
                ],
            });
        } else {
            // Second batch with channels:public returns msg_3.
            assert.deepEqual(JSON.parse(args.data.narrow), [
                {operator: "channels", operand: "public"},
            ]);
            assert.equal(args.data.message_ids, JSON.stringify([3]));
            args.success({
                messages: [
                    {id: 3, content_type: "text/x-markdown", content: "Unsubscribed content"},
                ],
            });
        }
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2, 3],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
        /* istanbul ignore next */
        on_error() {
            error_called = true;
        },
    });

    assert.ok(success_called);
    assert.equal(error_called, false);
    assert.equal(channel_get_call_count, 2, "First batch + channels:public retry");
    assert.deepEqual(success_call_args, [
        "Already hydrated content",
        "Fetched markdown content",
        "Unsubscribed content",
    ]);
    // raw_content is not cached for messages from unsubscribed channels.
    assert.equal(msg_3.raw_content, undefined);

    // Case: Both batch calls miss a message (e.g. pre-subscription
    // message in a private channel with shared history). The
    // single-message endpoint should be used as a final fallback.
    const msg_4 = {
        id: 4,
        content: "<p>Private shared history</p>",
        type: "stream",
        stream_id: private_shared.stream_id,
    };

    reset_raw_content([1, 2, 3, 4]);
    add_messages_to_message_store([msg_1, msg_2, msg_3, msg_4]);
    success_called = false;
    error_called = false;
    channel_get_call_count = 0;

    override(channel, "get", (args) => {
        channel_get_call_count += 1;
        if (args.url === "/json/messages" && args.data.narrow === undefined) {
            // First batch returns msg_1, msg_2 only.
            args.success({
                messages: [
                    {id: 1, content_type: "text/x-markdown", content: "Fetched markdown content 1"},
                    {id: 2, content_type: "text/x-markdown", content: "Fetched markdown content 2"},
                ],
            });
        } else if (args.url === "/json/messages") {
            // channels:public retry returns msg_3 but not msg_4
            // (private channel).
            args.success({
                messages: [
                    {id: 3, content_type: "text/x-markdown", content: "Unsubscribed content"},
                ],
            });
        } else {
            // Individual fallback for msg_4.
            assert.equal(args.url, "/json/messages/4");
            args.success({
                message: {
                    content_type: "text/x-markdown",
                    content: "Private shared history content",
                },
            });
        }
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2, 3, 4],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
        /* istanbul ignore next */
        on_error() {
            error_called = true;
        },
    });

    assert.ok(success_called);
    assert.equal(error_called, false);
    assert.equal(channel_get_call_count, 3, "Two batch calls + one individual fallback");
    assert.deepEqual(success_call_args, [
        "Fetched markdown content 1",
        "Fetched markdown content 2",
        "Unsubscribed content",
        "Private shared history content",
    ]);

    // Case: Network error during hydration (first batch call fails).
    success_called = false;
    error_called = false;

    override(channel, "get", (args) => {
        args.error();
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2, 3],
        /* istanbul ignore next */
        on_success() {
            success_called = true;
        },
        on_error() {
            error_called = true;
        },
    });

    assert.equal(success_called, false);
    assert.ok(error_called, "Should call on_error if the network request fails");

    // Case: Individual fallback call fails.
    success_called = false;
    error_called = false;

    channel_get_call_count = 0;
    override(channel, "get", (args) => {
        channel_get_call_count += 1;
        if (args.url === "/json/messages") {
            // Both batch calls return nothing.
            args.success({messages: []});
        } else {
            args.error();
        }
    });

    reset_raw_content([2]);
    add_messages_to_message_store([msg_1, msg_2, msg_3]);

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2, 3],
        /* istanbul ignore next */
        on_success() {
            success_called = true;
        },
        on_error() {
            error_called = true;
        },
    });

    assert.equal(success_called, false);
    assert.ok(error_called, "Should call on_error if a fallback request fails");
});

run_test("get_raw_content_for_single_message", ({override}) => {
    const msg_1 = {
        id: 1,
        raw_content: "Already hydrated content",
        type: "stream",
        stream_id: denmark.stream_id,
    };
    const msg_2 = {
        id: 2,
        content: "<p>HTML content</p>",
        type: "stream",
        stream_id: denmark.stream_id,
    };
    const msg_3 = {
        id: 3,
        content: "<p>Error</p>",
        type: "stream",
        stream_id: social.stream_id,
    };

    add_messages_to_message_store([msg_1, msg_2, msg_3]);

    let success_called = false;
    let error_called = false;
    let success_call_args;

    // Case: The message already has raw_content.
    message_fetch_raw_content.get_raw_content_for_single_message({
        message_id: 1,
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });
    assert.ok(success_called);
    assert.equal(success_call_args, msg_1.raw_content);

    // Case: The network request succeeds.
    let channel_get_args;
    override(channel, "get", (args) => {
        channel_get_args = args;
        args.success({
            message: {content_type: "text/x-markdown", content: "Fetched markdown content"},
        });
    });

    message_fetch_raw_content.get_raw_content_for_single_message({
        message_id: 2,
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });
    assert.ok(success_called);
    // Uses the single-message endpoint, not the batch endpoint, so that
    // messages from unsubscribed channels can be fetched.
    assert.equal(channel_get_args.url, "/json/messages/2");
    assert.equal(success_call_args, "Fetched markdown content");
    assert.equal(success_call_args, msg_2.raw_content);

    // Case: Message from an unsubscribed channel. The fetch should
    // succeed, but raw_content should not be cached.
    success_called = false;
    override(channel, "get", (args) => {
        channel_get_args = args;
        args.success({
            message: {content_type: "text/x-markdown", content: "Unsubscribed content"},
        });
    });

    message_fetch_raw_content.get_raw_content_for_single_message({
        message_id: 3,
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });
    assert.ok(success_called);
    assert.equal(channel_get_args.url, "/json/messages/3");
    assert.equal(success_call_args, "Unsubscribed content");
    // raw_content is not cached for messages from unsubscribed channels.
    assert.equal(msg_3.raw_content, undefined);

    // Case: The network request fails/times out.
    error_called = false;
    override(channel, "get", (args) => {
        args.error();
    });

    message_fetch_raw_content.get_raw_content_for_single_message({
        message_id: 3,
        /* istanbul ignore next */
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
        on_error() {
            error_called = true;
        },
    });
    assert.ok(error_called);
});
