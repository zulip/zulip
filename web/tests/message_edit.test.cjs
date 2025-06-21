"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const message_edit = zrequire("message_edit");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");

const is_content_editable = message_edit.is_content_editable;

const settings_data = mock_esm("../src/settings_data");
const stream_data = mock_esm("../src/stream_data");

const realm = {};
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
    delete message.submessages;
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
    override(stream_data, "is_stream_archived", () => false);
    override(stream_data, "user_can_move_messages_within_channel", () => true);
    override(stream_data, "get_sub_by_id", () => ({}));
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
    override(settings_data, "user_can_move_messages_between_streams", () => true);
    override(current_user, "is_moderator", true);
    override(stream_data, "is_stream_archived", () => false);

    assert.equal(message_edit.is_stream_editable(message), false);

    message.locally_echoed = false;
    message.failed_request = true;
    assert.equal(message_edit.is_stream_editable(message), false);

    message.failed_request = false;
    assert.equal(message_edit.is_stream_editable(message), true);

    message.sent_by_me = false;
    assert.equal(message_edit.is_stream_editable(message), true);

    override(settings_data, "user_can_move_messages_between_streams", () => false);
    assert.equal(message_edit.is_stream_editable(message), false);

    override(current_user, "is_moderator", false);
    assert.equal(message_edit.is_stream_editable(message), false);

    override(realm, "realm_move_messages_between_streams_limit_seconds", 259200);
    message.timestamp = current_timestamp - 60;

    override(settings_data, "user_can_move_messages_between_streams", () => true);
    assert.equal(message_edit.is_stream_editable(message), true);

    message.timestamp = current_timestamp - 600000;
    assert.equal(message_edit.is_stream_editable(message), false);

    override(current_user, "is_moderator", true);
    assert.equal(message_edit.is_stream_editable(message), true);
});

run_test("get_deletability", ({override}) => {
    override(current_user, "is_admin", true);
    override(settings_data, "user_can_delete_any_message", () => true);
    override(settings_data, "user_can_delete_own_message", () => false);
    override(realm, "realm_message_content_delete_limit_seconds", null);
    const test_user = {
        user_id: 1,
        full_name: "Test user",
        email: "test@zulip.com",
    };
    people.add_active_user(test_user);

    const bot_user = {
        user_id: 2,
        is_bot: true,
        full_name: "Test bot user",
        email: "test-bot@zulip.com",
        bot_owner_id: 1,
    };
    people.add_active_user(bot_user);

    const message = {
        sent_by_me: false,
        locally_echoed: true,
        sender_id: 1,
    };

    // User can delete any message
    assert.equal(message_edit.get_deletability(message), true);

    override(settings_data, "user_can_delete_any_message", () => false);
    // User can't delete message sent by others
    assert.equal(message_edit.get_deletability(message), false);

    // Locally echoed messages are not deletable
    message.sent_by_me = true;
    assert.equal(message_edit.get_deletability(message), false);

    message.locally_echoed = false;
    assert.equal(message_edit.get_deletability(message), false);

    override(settings_data, "user_can_delete_own_message", () => true);
    assert.equal(message_edit.get_deletability(message), true);

    message.sent_by_me = false;
    assert.equal(message_edit.get_deletability(message), false);
    message.sent_by_me = true;

    let now = new Date();
    let current_timestamp = now / 1000;
    message.timestamp = current_timestamp - 5;

    override(realm, "realm_message_content_delete_limit_seconds", 10);
    assert.equal(message_edit.get_deletability(message), true);

    message.timestamp = current_timestamp - 60;
    assert.equal(message_edit.get_deletability(message), false);

    message.sender_id = 2;
    message.sent_by_me = false;
    people.initialize_current_user(test_user.user_id);
    override(realm, "realm_message_content_delete_limit_seconds", null);

    override(settings_data, "user_can_delete_own_message", () => true);
    assert.equal(message_edit.get_deletability(message), true);

    override(settings_data, "user_can_delete_own_message", () => false);
    assert.equal(message_edit.get_deletability(message), false);

    now = new Date();
    current_timestamp = now / 1000;
    override(realm, "realm_message_content_delete_limit_seconds", 10);
    message.timestamp = current_timestamp - 60;
    override(settings_data, "user_can_delete_own_message", () => true);
    assert.equal(message_edit.get_deletability(message), false);
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
