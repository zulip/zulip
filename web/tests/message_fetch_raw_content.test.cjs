"use strict";

const assert = require("node:assert/strict");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = zrequire("stream_data");
const message_store = zrequire("message_store");
const message_fetch = mock_esm("../src/message_fetch");
const narrow_state = mock_esm("../src/narrow_state");
const channel = mock_esm("../src/channel");
const message_fetch_raw_content = zrequire("message_fetch_raw_content");

function add_messages_to_message_store(messages) {
    message_store.clear_for_testing();
    for (const message of messages) {
        message_store.update_message_cache({message});
    }
}

// We only rely on message_fetch for type validation and narrow encoding.
message_fetch.message_ids_response_schema = {
    parse: (data) => data,
};
message_fetch.get_narrow_for_message_fetch = () => "";

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

stream_data.add_sub_for_tests(denmark);
stream_data.add_sub_for_tests(social);

run_test("get_raw_content_for_messages", ({override}) => {
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

    // Case: Fetching missing raw_content successfully, with the current
    // narrow passed so include_history can cover historical messages.
    let channel_get_args;
    success_called = false;
    error_called = false;

    const fake_filter = {};
    const encoded_narrow = JSON.stringify([{operator: "channel", operand: social.stream_id}]);
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", (filter) => {
        assert.equal(filter, fake_filter);
        return encoded_narrow;
    });
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
    assert.equal(channel_get_args.data.narrow, encoded_narrow);
    // It is safe to update raw_content for messages from channels
    // the user is subscribed to.
    assert.equal(msg_2.raw_content, "Fetched markdown content");
    assert.ok(success_called, "Should call on_success after successfully hydrating");
    assert.deepEqual(success_call_args, [msg_1.raw_content, msg_2.raw_content]);

    // Case: Encoded narrow is empty — omit the narrow parameter.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", () => "");
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

    assert.equal(channel_get_args.data.narrow, undefined);
    assert.ok(success_called);

    // Case: No current filter (e.g. recent conversations) — no narrow param.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => undefined);
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

    assert.equal(channel_get_args.data.narrow, undefined);
    assert.ok(success_called);

    // Case: Network error during hydration
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
});

// Separate test so we exercise the module-level default
// get_narrow_for_message_fetch (returns "") without a prior override
// of that function in the same test.
run_test("get_raw_content_for_messages module default narrow helper", ({override}) => {
    const msg_1 = {
        id: 1,
        content: "<p>HTML content</p>",
        type: "stream",
        stream_id: denmark.stream_id,
    };
    add_messages_to_message_store([msg_1]);

    let channel_get_args;
    const fake_filter = {};
    override(narrow_state, "filter", () => fake_filter);
    override(channel, "get", (args) => {
        channel_get_args = args;
        args.success({
            messages: [
                {id: 1, content_type: "text/x-markdown", content: "Fetched markdown content"},
            ],
        });
    });

    let success_called = false;
    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1],
        on_success() {
            success_called = true;
        },
    });

    assert.ok(success_called);
    assert.equal(channel_get_args.data.narrow, undefined);
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
