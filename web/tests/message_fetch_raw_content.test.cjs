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
    is_muted: true,
    invite_only: true,
    history_public_to_subscribers: true,
    can_add_subscribers_group: [],
    can_administer_channel_group: [],
    can_subscribe_group: [],
};

const social = {
    subscribed: false,
    color: "red",
    name: "social",
    stream_id: 2,
    is_muted: false,
    invite_only: true,
    history_public_to_subscribers: false,
    can_add_subscribers_group: [],
    can_administer_channel_group: [],
    can_subscribe_group: [],
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

    message_fetch_raw_content.get_raw_content_for_messages([1], () => {
        success_called = true;
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

    message_fetch_raw_content.get_raw_content_for_messages([1, 2], (args) => {
        success_called = true;
        success_call_args = args;
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

    // Case: Network error during hydration
    success_called = false;
    error_called = false;

    override(channel, "get", (args) => {
        args.error();
    });

    message_fetch_raw_content.get_raw_content_for_messages(
        [1, 2, 3],
        /* istanbul ignore next */
        () => {
            success_called = true;
        },
        () => {
            error_called = true;
        },
    );

    assert.equal(success_called, false);
    assert.ok(error_called, "Should call on_error if the network request fails");
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
    message_fetch_raw_content.get_raw_content_for_single_message(1, (args) => {
        success_called = true;
        success_call_args = args;
    });
    assert.ok(success_called);
    assert.equal(success_call_args, msg_1.raw_content);

    // Case: The network request succeeds.
    override(channel, "get", (args) => {
        args.success({
            messages: [
                {id: 2, content_type: "text/x-markdown", content: "Fetched markdown content"},
            ],
        });
    });

    message_fetch_raw_content.get_raw_content_for_single_message(2, (args) => {
        success_called = true;
        success_call_args = args;
    });
    assert.ok(success_called);
    assert.equal(success_call_args, "Fetched markdown content");
    assert.equal(success_call_args, msg_2.raw_content);

    // Case: The network request fails/times out.
    override(channel, "get", (args) => {
        args.error();
    });

    message_fetch_raw_content.get_raw_content_for_single_message(
        3,
        /* istanbul ignore next */
        (args) => {
            success_called = true;
            success_call_args = args;
        },
        () => {
            error_called = true;
        },
    );
    assert.ok(error_called);
});
