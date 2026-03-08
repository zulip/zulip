"use strict";

const assert = require("node:assert/strict");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const compose_reply = zrequire("compose_reply");
const message_store = zrequire("message_store");
const message_fetch_raw_content = mock_esm("../src/message_fetch_raw_content");
const compose_paste = mock_esm("../src/compose_paste");

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

run_test("process_quote_assets_for_messages", ({override}) => {
    // Case: We get back the raw_content.
    const msg_hydrated = {id: 1, raw_content: "Raw markdown", content: "<p>Raw markdown</p>"};
    const msg_unhydrated = {id: 2, content: "<p>unhydrated</p>"};

    add_messages_to_message_store([msg_hydrated, msg_unhydrated]);

    override(
        message_fetch_raw_content,
        "get_raw_content_for_messages",
        (_ids, on_success, _on_error) => {
            on_success(["Raw markdown", "hydrated"]);
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
        {message: msg_unhydrated, quote_content: "hydrated"},
        "Should use raw_content when available",
    );

    // Case: Network error on trying to get raw_content.
    // Here, we should use `message.raw_content` if it's available.
    // Else we fallback to using the local paste_handler_converter.
    override(
        message_fetch_raw_content,
        "get_raw_content_for_messages",
        (_ids, _on_success, on_error) => {
            on_error();
        },
    );

    override(
        compose_paste,
        "paste_handler_converter",
        (content) => `converted_by_turndown: ${content}`,
    );

    compose_reply.process_quote_assets_for_messages([1, 2], (assets) => {
        result_assets = assets;
    });

    assert.deepEqual(
        result_assets[0],
        {message: msg_hydrated, quote_content: "Raw markdown"},
        "Should use raw_content when available",
    );
    assert.deepEqual(
        result_assets[1],
        {message: msg_unhydrated, quote_content: "converted_by_turndown: <p>unhydrated</p>"},
        "Fallback to using paste_handler_converter",
    );
});
