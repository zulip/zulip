"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const message_edit = zrequire("message_edit");
const {set_current_user, set_realm} = zrequire("state_data");

const is_content_editable = message_edit.is_content_editable;

const compose_ui = mock_esm("../src/compose_ui");
const stream_data = mock_esm("../src/stream_data");

const realm = make_realm();
set_realm(realm);
const current_user = {};
set_current_user(current_user);

run_test("is_content_editable", ({override}) => {
    // You can't edit a null message
    assert.equal(is_content_editable(null), false);
    // You can't edit a message you didn't send
    assert.equal(
        is_content_editable({
            sent_by_me: false,
        }),
        false,
    );

    // Failed request are currently not editable (though we want to
    // change this back).
    assert.equal(
        is_content_editable({
            sent_by_me: true,
            failed_request: true,
        }),
        false,
    );

    // Locally echoed messages are not editable, since the message hasn't
    // finished being sent yet.
    assert.equal(
        is_content_editable({
            sent_by_me: true,
            locally_echoed: true,
        }),
        false,
    );

    // For the rest of these tests, we only consider messages sent by the
    // user, and that were successfully sent (i.e. no failed_request or local_id)
    const message = {
        sent_by_me: true,
        submessages: [],
    };

    override(realm, "realm_allow_message_editing", false);
    assert.equal(is_content_editable(message), false);

    override(realm, "realm_allow_message_editing", true);
    // Limit of 0 means no time limit on editing messages
    override(realm, "realm_message_content_edit_limit_seconds", null);
    assert.equal(is_content_editable(message), true);

    override(realm, "realm_message_content_edit_limit_seconds", 10);
    const now = new Date();
    const current_timestamp = now / 1000;
    message.timestamp = current_timestamp - 60;
    // Have 55+10 > 60 seconds from message.timestamp to edit the message; we're good!
    assert.equal(is_content_editable(message, 55), true);
    // It's been 60 > 45+10 since message.timestamp. When realm_allow_message_editing
    // is true, we can edit the topic if there is one.
    assert.equal(is_content_editable(message, 45), false);
    // Right now, we prevent users from editing widgets.
    message.submessages = ["/poll"];
    assert.equal(is_content_editable(message, 55), false);
    message.submessages = [];
    message.type = "private";
    assert.equal(is_content_editable(message, 45), false);

    assert.equal(is_content_editable(message, 55), true);
    // If we don't pass a second argument, treat it as 0
    assert.equal(is_content_editable(message), false);
});

run_test("is_topic_editable", ({override}) => {
    const now = new Date();
    const current_timestamp = now / 1000;

    const message = {
        sent_by_me: true,
        locally_echoed: true,
        type: "stream",
    };
    override(realm, "realm_allow_message_editing", true);
    override(stream_data, "is_stream_archived_by_id", () => false);
    override(stream_data, "user_can_move_messages_within_channel", () => true);
    override(stream_data, "get_sub_by_id", () => ({}));
    override(stream_data, "is_empty_topic_only_channel", () => false);
    override(current_user, "is_moderator", true);

    assert.equal(message_edit.is_topic_editable(message), false);

    message.locally_echoed = false;
    message.failed_request = true;
    assert.equal(message_edit.is_topic_editable(message), false);

    message.failed_request = false;
    assert.equal(message_edit.is_topic_editable(message), true);

    message.sent_by_me = false;
    assert.equal(message_edit.is_topic_editable(message), true);

    override(stream_data, "user_can_move_messages_within_channel", () => false);
    assert.equal(message_edit.is_topic_editable(message), false);

    override(current_user, "is_moderator", false);
    assert.equal(message_edit.is_topic_editable(message), false);

    message.topic = "translated: (no topic)";
    assert.equal(message_edit.is_topic_editable(message), false);

    message.topic = "test topic";
    override(stream_data, "user_can_move_messages_within_channel", () => false);
    assert.equal(message_edit.is_topic_editable(message), false);

    override(realm, "realm_move_messages_within_stream_limit_seconds", 259200);
    message.timestamp = current_timestamp - 60;

    override(stream_data, "user_can_move_messages_within_channel", () => true);
    assert.equal(message_edit.is_topic_editable(message), true);

    message.timestamp = current_timestamp - 600000;
    assert.equal(message_edit.is_topic_editable(message), false);

    override(current_user, "is_moderator", true);
    assert.equal(message_edit.is_topic_editable(message), true);

    override(realm, "realm_allow_message_editing", false);
    assert.equal(message_edit.is_topic_editable(message), true);
});

run_test("is_stream_editable", ({override}) => {
    const now = new Date();
    const current_timestamp = now / 1000;

    const message = {
        sent_by_me: true,
        locally_echoed: true,
        type: "stream",
    };
    override(realm, "realm_allow_message_editing", true);
    override(stream_data, "user_can_move_messages_out_of_channel", () => true);
    override(stream_data, "get_sub_by_id", () => ({}));
    override(current_user, "is_moderator", true);
    override(stream_data, "is_stream_archived_by_id", () => false);

    assert.equal(message_edit.is_stream_editable(message), false);

    message.locally_echoed = false;
    message.failed_request = true;
    assert.equal(message_edit.is_stream_editable(message), false);

    message.failed_request = false;
    assert.equal(message_edit.is_stream_editable(message), true);

    message.sent_by_me = false;
    assert.equal(message_edit.is_stream_editable(message), true);

    override(stream_data, "user_can_move_messages_out_of_channel", () => false);
    assert.equal(message_edit.is_stream_editable(message), false);

    override(current_user, "is_moderator", false);
    assert.equal(message_edit.is_stream_editable(message), false);

    override(realm, "realm_move_messages_between_streams_limit_seconds", 259200);
    message.timestamp = current_timestamp - 60;

    override(stream_data, "user_can_move_messages_out_of_channel", () => true);
    assert.equal(message_edit.is_stream_editable(message), true);

    message.timestamp = current_timestamp - 600000;
    assert.equal(message_edit.is_stream_editable(message), false);

    override(current_user, "is_moderator", true);
    assert.equal(message_edit.is_stream_editable(message), true);
});

run_test("stream_and_topic_exist_in_edit_history", () => {
    // A message with no edit history should always return false;
    // the message's current stream_id and topic are not compared
    // to the stream_id and topic parameters.
    const message_no_edits = {
        stream_id: 1,
        type: "stream",
        topic: "topic match",
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_no_edits, 2, "no match"),
        false,
    );
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_no_edits, 1, "topic match"),
        false,
    );

    // A non-stream message (object has no stream_id or topic)
    // with content edit history, should return false.
    const private_message = {
        edit_history: [{prev_content: "content edit to direct message"}],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(private_message, 1, "topic match"),
        false,
    );

    // A stream message with only content edits should return false,
    // even if the message's current stream_id and topic are a match.
    const message_content_edit = {
        stream_id: 1,
        type: "stream",
        topic: "topic match",
        edit_history: [{prev_content: "content edit"}],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_content_edit, 1, "topic match"),
        false,
    );

    const message_stream_edit = {
        stream_id: 6,
        type: "stream",
        topic: "topic match",
        edit_history: [{stream: 6, prev_stream: 1}],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_stream_edit, 2, "topic match"),
        false,
    );
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_stream_edit, 1, "topic match"),
        true,
    );

    const message_topic_edit = {
        stream_id: 1,
        type: "stream",
        topic: "final topic",
        edit_history: [{topic: "final topic", prev_topic: "topic match"}],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_topic_edit, 1, "no match"),
        false,
    );
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_topic_edit, 1, "topic match"),
        true,
    );

    const message_many_edits = {
        stream_id: 6,
        type: "stream",
        topic: "final topic",
        edit_history: [
            {stream: 6, prev_stream: 5},
            {prev_content: "content only edit"},
            {topic: "final topic", prev_topic: "topic match"},
            {stream: 5, prev_stream: 1},
        ],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_many_edits, 1, "no match"),
        false,
    );
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_many_edits, 2, "topic match"),
        false,
    );
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_many_edits, 1, "topic match"),
        true,
    );

    // When the topic and stream_id exist in the message's edit history
    // individually, but not together in a historical state, it should return false.
    const message_no_historical_match = {
        stream_id: 6,
        type: "stream",
        topic: "final topic",
        edit_history: [
            {stream: 6, prev_stream: 1}, // stream matches, topic does not
            {stream: 1, prev_stream: 5}, // neither match
            {topic: "final topic", prev_topic: "topic match"}, // topic matches, stream does not
        ],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(
            message_no_historical_match,
            1,
            "topic match",
        ),
        false,
    );
});

run_test("update_preview_embeds", ({override}) => {
    const content = "http://example.com/";
    const rendered_content = "<p>message with an embed</p>";
    const $row = $.create("message row being edited");
    const $message_edit_content = $.create("textarea.message_edit_content");
    $message_edit_content.set_closest_results(".message_row", $row);
    message_edit.currently_editing_messages.set(17, $message_edit_content);

    const applied_to = [];
    override(compose_ui, "apply_embeds_to_preview", ($preview_container) => {
        applied_to.push($preview_container.selector);
    });

    // The message has been edited since the fetch: the update is dropped.
    $message_edit_content.val("http://example.com/ edited");
    message_edit.update_preview_embeds(content, rendered_content);
    assert.equal(applied_to.length, 0);

    // The edit box still holds the content that was rendered.
    $message_edit_content.val(content);
    message_edit.update_preview_embeds(content, rendered_content);
    assert.deepEqual(applied_to, ["message row being edited"]);

    message_edit.currently_editing_messages.clear();
});
