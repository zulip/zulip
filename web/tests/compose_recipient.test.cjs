"use strict";

const {strict: assert} = require("node:assert");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const {set_realm} = zrequire("state_data");
const compose_state = zrequire("compose_state");

const stream_topic_history = mock_esm("../src/stream_topic_history", {
    get_recent_topic_names: noop,
    has_history_for: noop,
});

const stream_data = mock_esm("../src/stream_data", {
    can_use_empty_topic: noop,
    is_empty_topic_only_channel: noop,
    can_create_new_topics_in_stream: noop,
});

set_global("document", "document-stub");
set_realm(make_realm({realm_empty_topic_display_name: "general chat"}));

const compose_recipient = zrequire("compose_recipient");

run_test("restricted user, no empty topic shows Topic placeholder", ({override}) => {
    const test_stream_id = 42;

    // Setup jQuery elements
    const $input = $("input#stream_message_recipient_topic");
    $("#topic-not-mandatory-placeholder").hide = noop;
    $("textarea#compose-textarea").trigger = noop;
    $("#compose-channel-recipient").removeClass = noop;
    $(".compose_select_recipient-dropdown-list-container").length = 0;

    // Setup stream
    compose_state.set_stream_id(test_stream_id);
    compose_state.topic("");

    // User cannot create new topics
    override(stream_data, "can_create_new_topics_in_stream", () => false);
    // Empty topics ARE allowed in this stream
    override(stream_data, "can_use_empty_topic", () => true);
    override(stream_data, "is_empty_topic_only_channel", () => false);
    // Stream has topic history
    override(stream_topic_history, "has_history_for", () => true);
    // No empty topic exists in this stream
    override(stream_topic_history, "get_recent_topic_names", () => [
        "existing topic 1",
        "existing topic 2",
    ]);

    // Call the function
    compose_recipient.update_topic_displayed_text();

    // Assert: Placeholder should be "Topic"
    assert.equal($input.attr("placeholder"), "translated: Topic");
});

run_test("restricted user, empty topic exists allows general chat", ({override}) => {
    const test_stream_id = 43;

    // Setup jQuery elements
    const $input = $("input#stream_message_recipient_topic");
    $("#topic-not-mandatory-placeholder").hide = noop;
    $("textarea#compose-textarea").trigger = noop;
    $("#compose-channel-recipient").removeClass = noop;
    $(".compose_select_recipient-dropdown-list-container").length = 0;

    // Setup stream
    compose_state.set_stream_id(test_stream_id);
    compose_state.topic("");

    // User cannot create new topics
    override(stream_data, "can_create_new_topics_in_stream", () => false);
    // Empty topics ARE allowed in this stream
    override(stream_data, "can_use_empty_topic", () => true);
    override(stream_data, "is_empty_topic_only_channel", () => false);
    // Stream has topic history
    override(stream_topic_history, "has_history_for", () => true);
    // Empty topic DOES exist in this stream
    override(stream_topic_history, "get_recent_topic_names", () => ["", "existing topic 1"]);

    // Call the function
    compose_recipient.update_topic_displayed_text();

    // Assert: Placeholder should NOT be "Topic"
    assert.notEqual($input.attr("placeholder"), "translated: Topic");
});
