"use strict";

const assert = require("node:assert/strict");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const stream_data = zrequire("stream_data");
const compose_reply = zrequire("compose_reply");
const message_store = zrequire("message_store");
const channel = mock_esm("../src/channel");
const compose_paste = mock_esm("../src/compose_paste");
const message_fetch = mock_esm("../src/message_fetch");

const pm_user_ids_1 = "1,2";
const pm_user_ids_2 = "3,4";

const msg_pm_1 = {type: "private", to_user_ids: pm_user_ids_1};
const msg_pm_2 = {type: "private", to_user_ids: pm_user_ids_1};
const msg_pm_3 = {type: "private", to_user_ids: pm_user_ids_2};

const msg_stream_denmark_general = {type: "stream", stream_id: 10, topic: "general"};
// Topic case should be ignored by all_messages_have_same_recipient
const msg_stream_denmark_general_caps = {type: "stream", stream_id: 10, topic: "GENERAL"};
const msg_stream_denmark_design = {type: "stream", stream_id: 10, topic: "design"};
const msg_stream_sweden_general = {type: "stream", stream_id: 20, topic: "general"};

function add_messages_to_message_store(messages) {
    message_store.clear_for_testing();
    for (const message of messages) {
        message_store.update_message_cache({message});
    }
}

run_test("all_messages_have_same_recipient", () => {
    // Assertions on empty arrays
    assert.throws(() => compose_reply.all_messages_have_same_recipient([]), Error);

    // Private messages
    assert.ok(compose_reply.all_messages_have_same_recipient([msg_pm_1]));
    assert.ok(compose_reply.all_messages_have_same_recipient([msg_pm_1, msg_pm_2]));
    assert.equal(
        compose_reply.all_messages_have_same_recipient([msg_pm_1, msg_pm_2, msg_pm_3]),
        false,
        "Fails if private message recipients differ",
    );

    // Stream messages
    assert.ok(compose_reply.all_messages_have_same_recipient([msg_stream_denmark_general]));
    assert.ok(
        compose_reply.all_messages_have_same_recipient([
            msg_stream_denmark_general,
            msg_stream_denmark_general_caps,
        ]),
        "Topic matching should be case-insensitive",
    );

    assert.equal(
        compose_reply.all_messages_have_same_recipient([
            msg_stream_denmark_general,
            msg_stream_denmark_design,
        ]),
        false,
        "Return false if topics differ",
    );
    assert.equal(
        compose_reply.all_messages_have_same_recipient([
            msg_stream_denmark_general,
            msg_stream_sweden_general,
        ]),
        false,
        "Return false if stream IDs differ for channel messages",
    );

    // Mixed types
    assert.equal(
        compose_reply.all_messages_have_same_recipient([msg_pm_1, msg_stream_denmark_general]),
        false,
        "Return false on mixed stream/private messages",
    );
    assert.equal(
        compose_reply.all_messages_have_same_recipient([msg_stream_denmark_general, msg_pm_1]),
        false,
        "Return false on mixed stream/private messages",
    );
});

run_test("all_messages_have_same_channel", () => {
    // Assertions on empty arrays
    assert.throws(() => compose_reply.all_messages_have_same_channel([]), Error);

    assert.equal(compose_reply.all_messages_have_same_channel([msg_pm_1]), false);
    assert.equal(
        compose_reply.all_messages_have_same_channel([msg_pm_1, msg_stream_denmark_general]),
        false,
    );

    // Stream messages
    assert.ok(compose_reply.all_messages_have_same_channel([msg_stream_denmark_general]));
    assert.ok(
        compose_reply.all_messages_have_same_channel([
            msg_stream_denmark_general,
            msg_stream_denmark_design,
        ]),
        "Returns true for same stream ID, even if topics differ",
    );
    assert.equal(
        compose_reply.all_messages_have_same_channel([
            msg_stream_denmark_general,
            msg_stream_sweden_general,
        ]),
        false,
        "Return false if stream IDs differ",
    );

    // Mixed types where first is stream
    assert.equal(
        compose_reply.all_messages_have_same_channel([msg_stream_denmark_general, msg_pm_1]),
        false,
    );
});

run_test("all_messages_are_private", () => {
    // Assertions on empty arrays
    assert.throws(() => compose_reply.all_messages_are_private([]), Error);

    // Stream messages immediately return false
    assert.equal(compose_reply.all_messages_are_private([msg_stream_denmark_general]), false);
    assert.equal(
        compose_reply.all_messages_are_private([msg_stream_denmark_general, msg_pm_1]),
        false,
    );

    // Private messages
    assert.ok(compose_reply.all_messages_are_private([msg_pm_1]));
    assert.ok(
        compose_reply.all_messages_are_private([msg_pm_1, msg_pm_3]),
        "Returns true for private messages even if recipients differ",
    );

    // Mixed types where first is private
    assert.equal(
        compose_reply.all_messages_are_private([msg_pm_1, msg_stream_denmark_general]),
        false,
    );
});

run_test("get_quote_context_for_message", () => {
    const msg_alice = {type: "stream", stream_id: 10, topic: "general", sender_id: 1};
    const msg_alice_2 = {type: "stream", stream_id: 10, topic: "general", sender_id: 1};
    const msg_bob = {type: "stream", stream_id: 10, topic: "general", sender_id: 2};
    const msg_bob_design = {type: "stream", stream_id: 10, topic: "design", sender_id: 2};

    const pm_alice = {type: "private", to_user_ids: "1,2", sender_id: 1};
    const pm_alice_2 = {type: "private", to_user_ids: "1,2", sender_id: 1};
    const pm_bob = {type: "private", to_user_ids: "1,2", sender_id: 2};
    const pm_charlie = {type: "private", to_user_ids: "1,2,3", sender_id: 3};

    // First message in a quote chain
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: msg_alice,
            previous_message: msg_alice_2,
            forward_message: false,
            is_first_message_from_quote_chain: true,
        }),
        "INCLUDE_SENDER_AND_RECIPIENT",
    );

    // Continuous stream message from the same sender
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: msg_alice_2,
            previous_message: msg_alice,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_NOTHING",
    );

    // Continuous private message from the same sender
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: pm_alice_2,
            previous_message: pm_alice,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_NOTHING",
    );

    // Same stream thread, but the sender changed
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: msg_bob,
            previous_message: msg_alice,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_SENDER",
    );

    // Same private message thread, but the sender changed
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: pm_bob,
            previous_message: pm_alice,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_SENDER",
    );

    // Stream/topic changed completely
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: msg_bob_design,
            previous_message: msg_alice,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_SENDER_AND_RECIPIENT",
    );

    // Private message recipients changed completely
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: pm_charlie,
            previous_message: pm_alice,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_SENDER_AND_RECIPIENT",
    );

    // Quoted individually (no previous message)
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: msg_alice,
            previous_message: undefined,
            forward_message: false,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_SENDER",
    );

    // Forwarded individually
    assert.equal(
        compose_reply.get_quote_context_for_message({
            current_message: msg_alice,
            previous_message: undefined,
            forward_message: true,
            is_first_message_from_quote_chain: false,
        }),
        "INCLUDE_SENDER_AND_RECIPIENT",
    );
});

run_test("get_multi_message_quote_status", () => {
    const stream_1_general = {type: "stream", stream_id: 10, topic: "general"};
    const stream_1_general_2 = {type: "stream", stream_id: 10, topic: "general"};
    const stream_1_design = {type: "stream", stream_id: 10, topic: "design"};
    const stream_2_general = {type: "stream", stream_id: 20, topic: "general"};

    const pm_1 = {type: "private", to_user_ids: "1,2"};
    const pm_1_b = {type: "private", to_user_ids: "1,2"};
    const pm_2 = {type: "private", to_user_ids: "3,4"};

    assert.equal(
        compose_reply.get_multi_message_quote_status([stream_1_general, stream_1_general_2], false),
        "MESSAGES_WITH_SAME_RECIPIENT",
    );
    assert.equal(
        compose_reply.get_multi_message_quote_status([pm_1, pm_1_b], undefined),
        "MESSAGES_WITH_SAME_RECIPIENT",
    );

    assert.equal(
        compose_reply.get_multi_message_quote_status([stream_1_general, stream_1_design], false),
        "QUOTING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS",
    );

    assert.equal(
        compose_reply.get_multi_message_quote_status([stream_1_general, stream_1_design], true),
        "FORWARDING_MESSAGES_FROM_SAME_CHANNEL_AND_MULTIPLE_TOPICS",
    );

    assert.equal(
        compose_reply.get_multi_message_quote_status([pm_1, pm_2], false),
        "QUOTING_MESSAGES_FROM_DIFFERENT_DM_CONVERSATIONS",
    );

    // MESSAGES_WITH_NOTHING_IN_COMMON
    // 1. Belong to different channels.
    assert.equal(
        compose_reply.get_multi_message_quote_status([stream_1_general, stream_2_general], false),
        "MESSAGES_WITH_NOTHING_IN_COMMON",
    );

    // 2. Mixed channel and private messages
    assert.equal(
        compose_reply.get_multi_message_quote_status([stream_1_general, pm_1], false),
        "MESSAGES_WITH_NOTHING_IN_COMMON",
    );

    // 3. Different DM conversations while forwarding.
    assert.equal(
        compose_reply.get_multi_message_quote_status([pm_1, pm_2], true),
        "MESSAGES_WITH_NOTHING_IN_COMMON",
    );
});

// We only rely on message_fetch for type validation.
message_fetch.message_ids_response_schema = {
    parse: (data) => data,
};

run_test("maybe_hydrate_messages_with_raw_content", ({override}) => {
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

    compose_reply.maybe_hydrate_messages_with_raw_content([1], () => {
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

    compose_reply.maybe_hydrate_messages_with_raw_content([1, 2], () => {
        success_called = true;
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

    // Case: Network error during hydration
    success_called = false;
    error_called = false;

    override(channel, "get", (args) => {
        args.error();
    });

    compose_reply.maybe_hydrate_messages_with_raw_content(
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
    assert.equal(error_called, true);
    assert.ok(error_called, "Should call on_error if the network request fails");
});

run_test("process_quote_assets_for_messages", ({override, override_rewire}) => {
    const msg_hydrated = {id: 1, raw_content: "Raw markdown", content: "<p>Raw markdown</p>"};
    // This message won't have the cached raw_content after the
    // maybe_hydrate_messages_with_raw_content step, say because
    // it is from a source we won't be receiving message update
    // events for.
    const msg_fallback = {id: 2, content: "<p>HTML fallback</p>"};
    add_messages_to_message_store([msg_hydrated, msg_fallback]);

    override(
        compose_paste,
        "paste_handler_converter",
        (content) => `converted_by_turndown: ${content}`,
    );

    override_rewire(
        compose_reply,
        "maybe_hydrate_messages_with_raw_content",
        (_ids, on_success, _on_error) => {
            on_success();
        },
    );

    let result_assets = [];
    compose_reply.process_quote_assets_for_messages([1, 2], (assets) => {
        result_assets = assets;
    });

    assert.equal(result_assets.length, 2);

    assert.deepEqual(
        result_assets[0],
        {message: msg_hydrated, quote_content: "Raw markdown"},
        "Should use raw_content when available",
    );

    assert.deepEqual(
        result_assets[1],
        {message: msg_fallback, quote_content: "converted_by_turndown: <p>HTML fallback</p>"},
        "Should fallback to paste_handler_converter when raw_content is missing",
    );
});
