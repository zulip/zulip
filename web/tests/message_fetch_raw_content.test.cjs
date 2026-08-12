"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = zrequire("stream_data");
const message_store = zrequire("message_store");
const {Filter} = zrequire("filter");
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
    let success_call_args;

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1],
        on_success() {
            success_called = true;
        },
    });

    assert.ok(success_called, "Should call on_success immediately if all messages are hydrated");

    // Case: Fetching missing raw_content successfully. Only
    // history-enabling channel terms are passed for include_history.
    let channel_get_args;
    success_called = false;

    const fake_filter = {};
    const full_encoded_narrow = JSON.stringify([
        {operator: "channel", operand: social.stream_id},
        {operator: "topic", operand: "some-topic"},
        {operator: "is", operand: "unread"},
    ]);
    const history_only_narrow = JSON.stringify([{operator: "channel", operand: social.stream_id}]);
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", (filter) => {
        assert.equal(filter, fake_filter);
        return full_encoded_narrow;
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
    assert.equal(
        channel_get_args.data.narrow,
        history_only_narrow,
        "Should strip topic/is: and keep only channel for shared history",
    );
    // It is safe to update raw_content for messages from channels
    // the user is subscribed to.
    assert.equal(msg_2.raw_content, "Fetched markdown content");
    assert.ok(success_called, "Should call on_success after successfully hydrating");
    assert.deepEqual(success_call_args, [msg_1.raw_content, msg_2.raw_content]);

    // Case: channels:public is kept as history-enabling. Other terms are stripped.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", () =>
        JSON.stringify([
            {operator: "channels", operand: "public"},
            {operator: "search", operand: "keyword"},
        ]),
    );
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
        on_success() {
            success_called = true;
        },
    });

    assert.equal(
        channel_get_args.data.narrow,
        JSON.stringify([{operator: "channels", operand: "public"}]),
    );
    assert.ok(success_called);

    // Case: channels:web-public is kept as history-enabling.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", () =>
        JSON.stringify([{operator: "channels", operand: "web-public"}]),
    );
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
        on_success() {
            success_called = true;
        },
    });

    assert.equal(
        channel_get_args.data.narrow,
        JSON.stringify([{operator: "channels", operand: "web-public"}]),
    );
    assert.ok(success_called);

    // Case: For an is: operator, no history terms are present, so we omit narrow.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", () =>
        JSON.stringify([{operator: "is", operand: "starred"}]),
    );
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
        on_success() {
            success_called = true;
        },
    });

    assert.equal(channel_get_args.data.narrow, undefined);
    assert.ok(success_called);

    // Case: Negated channel terms are not history-enabling and are dropped.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => fake_filter);
    override(message_fetch, "get_narrow_for_message_fetch", () =>
        JSON.stringify([
            {operator: "channel", operand: social.stream_id, negated: true},
            {operator: "channel", operand: denmark.stream_id},
        ]),
    );
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
        on_success() {
            success_called = true;
        },
    });

    assert.equal(
        channel_get_args.data.narrow,
        JSON.stringify([{operator: "channel", operand: denmark.stream_id}]),
    );
    assert.ok(success_called);

    // Case: The encoded narrow is empty, so omit the narrow parameter.
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

    // Case: There is no current filter (e.g. recent conversations), so no narrow param.
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

    // Case: A partial batch response leaves explicit undefined for missing ids.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => undefined);
    override(channel, "get", (args) => {
        channel_get_args = args;
        args.success({
            messages: [],
        });
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });

    assert.ok(success_called);
    assert.equal(success_call_args.length, 2);
    assert.equal(success_call_args[0], msg_1.raw_content);
    // The slot is present as undefined.
    assert.equal(success_call_args[1], undefined);

    // Case: A partial batch where message_store gains raw_content during the request.
    success_called = false;
    delete msg_2.raw_content;
    override(narrow_state, "filter", () => undefined);
    override(channel, "get", (args) => {
        // Simulate another path hydrating message_store before success runs.
        msg_2.raw_content = "Hydrated in message_store mid-flight";
        args.success({messages: []});
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });

    assert.ok(success_called);
    assert.deepEqual(success_call_args, [
        msg_1.raw_content,
        "Hydrated in message_store mid-flight",
    ]);

    // Case: Mixed partial. One id is returned and one is missing (undefined slot).
    success_called = false;
    delete msg_2.raw_content;
    delete msg_3.raw_content;
    override(narrow_state, "filter", () => undefined);
    override(channel, "get", (args) => {
        args.success({
            messages: [{id: 2, content_type: "text/x-markdown", content: "only two"}],
        });
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [2, 3],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });

    assert.ok(success_called);
    assert.equal(success_call_args.length, 2);
    assert.equal(success_call_args[0], "only two");
    assert.equal(success_call_args[1], undefined);

    // Case: The server returns messages out of request order. The result
    // still matches message_ids order, with undefined for the missing middle id.
    success_called = false;
    delete msg_1.raw_content;
    delete msg_2.raw_content;
    delete msg_3.raw_content;
    // msg_1 is Denmark (subscribed); msg_3 is social (unsubscribed).
    add_messages_to_message_store([
        {
            id: 1,
            content: "<p>one html</p>",
            type: "stream",
            stream_id: denmark.stream_id,
        },
        {
            id: 2,
            content: "<p>two html</p>",
            type: "stream",
            stream_id: denmark.stream_id,
        },
        {
            id: 3,
            content: "<p>three html</p>",
            type: "stream",
            stream_id: social.stream_id,
        },
    ]);
    override(narrow_state, "filter", () => undefined);
    override(channel, "get", (args) => {
        assert.equal(args.data.message_ids, JSON.stringify([1, 2, 3]));
        // Deliberately reverse order and omit id 2.
        args.success({
            messages: [
                {id: 3, content_type: "text/x-markdown", content: "raw three"},
                {id: 1, content_type: "text/x-markdown", content: "raw one"},
            ],
        });
    });

    message_fetch_raw_content.get_raw_content_for_messages({
        message_ids: [1, 2, 3],
        on_success(args) {
            success_called = true;
            success_call_args = args;
        },
    });

    assert.ok(success_called);
    assert.deepEqual(success_call_args, ["raw one", undefined, "raw three"]);
    assert.equal(success_call_args.length, 3);
    assert.equal(success_call_args[1], undefined);

    // Case: Network error during hydration
    success_called = false;
    let error_called = false;

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

run_test("get_raw_content_for_messages encodes real Filter narrows", ({override}) => {
    const dm_user_a = make_user();
    const dm_user_b = make_user();
    const msg = {
        id: 2,
        content: "<p>HTML content</p>",
        type: "stream",
        stream_id: social.stream_id,
    };
    add_messages_to_message_store([msg]);

    let channel_get_args;
    override(channel, "get", (args) => {
        channel_get_args = args;
        args.success({
            messages: [
                {id: 2, content_type: "text/x-markdown", content: "Fetched markdown content"},
            ],
        });
    });
    override(message_fetch, "get_narrow_for_message_fetch", (filter) => {
        const terms = filter.public_terms().map((term) => {
            if (term.operator === "channel" && typeof term.operand === "string") {
                const stream = stream_data.get_sub_by_id_string(term.operand);
                if (stream !== undefined) {
                    return {...term, operand: stream.stream_id};
                }
            }
            return term;
        });
        return JSON.stringify(terms);
    });

    function fetch_narrow_for_filter(filter) {
        delete msg.raw_content;
        override(narrow_state, "filter", () => filter);
        let success_called = false;
        message_fetch_raw_content.get_raw_content_for_messages({
            message_ids: [2],
            on_success() {
                success_called = true;
            },
        });
        assert.ok(success_called);
        return channel_get_args.data.narrow;
    }

    // Channel + topic + is:unread keeps only channel; operand is coerced to int.
    assert.equal(
        fetch_narrow_for_filter(
            new Filter([
                {operator: "channel", operand: social.stream_id.toString()},
                {operator: "topic", operand: "some-topic"},
                {operator: "is", operand: "unread"},
            ]),
        ),
        JSON.stringify([{operator: "channel", operand: social.stream_id, negated: false}]),
    );

    // channels:public + search keeps only channels:public.
    assert.equal(
        fetch_narrow_for_filter(
            new Filter([
                {operator: "channels", operand: "public"},
                {operator: "search", operand: "keyword"},
            ]),
        ),
        JSON.stringify([{operator: "channels", operand: "public", negated: false}]),
    );

    // DM array operand must parse; it is not history-enabling, so omit narrow.
    assert.equal(
        fetch_narrow_for_filter(
            new Filter([{operator: "dm", operand: [dm_user_a.user_id, dm_user_b.user_id]}]),
        ),
        undefined,
    );

    // is:starred alone omits the narrow parameter.
    assert.equal(
        fetch_narrow_for_filter(new Filter([{operator: "is", operand: "starred"}])),
        undefined,
    );
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
    let error_called;
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
