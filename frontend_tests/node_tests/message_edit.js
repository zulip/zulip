"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {page_params} = require("../zjsunit/zpage_params");

page_params.realm_community_topic_editing_limit_seconds = 259200;

const message_edit = zrequire("message_edit");
const settings_config = zrequire("settings_config");

const get_editability = message_edit.get_editability;
const editability_types = message_edit.editability_types;

const settings_data = mock_esm("../../static/js/settings_data");

run_test("get_editability", ({override}) => {
    override(settings_data, "user_can_move_messages_to_another_topic", () => true);
    // You can't edit a null message
    assert.equal(get_editability(null), editability_types.NO);
    // You can't edit a message you didn't send
    assert.equal(
        get_editability({
            sent_by_me: false,
        }),
        editability_types.NO,
    );

    // Failed request are currently not editable (though we want to
    // change this back).
    assert.equal(
        get_editability({
            sent_by_me: true,
            failed_request: true,
        }),
        editability_types.NO,
    );

    // Locally echoed messages are not editable, since the message hasn't
    // finished being sent yet.
    assert.equal(
        get_editability({
            sent_by_me: true,
            locally_echoed: true,
        }),
        editability_types.NO,
    );

    // For the rest of these tests, we only consider messages sent by the
    // user, and that were successfully sent (i.e. no failed_request or local_id)
    let message = {
        sent_by_me: true,
    };

    page_params.realm_allow_message_editing = false;
    assert.equal(get_editability(message), editability_types.NO);

    page_params.realm_allow_message_editing = true;
    // Limit of 0 means no time limit on editing messages
    page_params.realm_message_content_edit_limit_seconds = null;
    assert.equal(get_editability(message), editability_types.CONTENT_ONLY);

    page_params.realm_message_content_edit_limit_seconds = 10;
    const now = new Date();
    const current_timestamp = now / 1000;
    message.timestamp = current_timestamp - 60;
    // Have 55+10 > 60 seconds from message.timestamp to edit the message; we're good!
    assert.equal(get_editability(message, 55), editability_types.CONTENT_ONLY);
    // It's been 60 > 45+10 since message.timestamp. When realm_allow_message_editing
    // is true, we can edit the topic if there is one.
    assert.equal(get_editability(message, 45), editability_types.NO);
    // Right now, we prevent users from editing widgets.
    message.submessages = ["/poll"];
    assert.equal(get_editability(message, 55), editability_types.NO);
    delete message.submessages;
    message.type = "private";
    assert.equal(get_editability(message, 45), editability_types.NO);

    assert.equal(get_editability(message, 55), editability_types.CONTENT_ONLY);
    // If we don't pass a second argument, treat it as 0
    assert.equal(get_editability(message), editability_types.NO);

    message = {
        sent_by_me: false,
        type: "stream",
    };
    page_params.realm_edit_topic_policy =
        settings_config.common_message_policy_values.by_everyone.code;
    page_params.realm_allow_message_editing = true;
    page_params.realm_message_content_edit_limit_seconds = null;
    page_params.realm_community_topic_editing_limit_seconds = 50;
    page_params.is_admin = false;
    message.timestamp = current_timestamp - 60;
    assert.equal(get_editability(message), editability_types.NO);

    page_params.is_admin = true;
    assert.equal(get_editability(message), editability_types.TOPIC_ONLY);

    page_params.is_admin = false;
    page_params.realm_community_topic_editing_limit_seconds = 259200;
    assert.equal(get_editability(message), editability_types.TOPIC_ONLY);

    message.sent_by_me = true;
    assert.equal(get_editability(message), editability_types.FULL);

    page_params.realm_allow_message_editing = false;
    assert.equal(get_editability(message), editability_types.TOPIC_ONLY);
});

run_test("is_topic_editable", ({override}) => {
    const now = new Date();
    const current_timestamp = now / 1000;

    const message = {
        sent_by_me: true,
        locally_echoed: true,
        type: "stream",
    };
    page_params.realm_allow_message_editing = true;
    override(settings_data, "user_can_move_messages_to_another_topic", () => true);
    page_params.is_admin = true;

    assert.equal(message_edit.is_topic_editable(message), false);

    message.locally_echoed = false;
    message.failed_request = true;
    assert.equal(message_edit.is_topic_editable(message), false);

    message.failed_request = false;
    assert.equal(message_edit.is_topic_editable(message), true);

    page_params.sent_by_me = false;
    assert.equal(message_edit.is_topic_editable(message), true);

    override(settings_data, "user_can_move_messages_to_another_topic", () => false);
    assert.equal(message_edit.is_topic_editable(message), false);

    page_params.is_admin = false;
    assert.equal(message_edit.is_topic_editable(message), false);

    message.topic = "translated: (no topic)";
    assert.equal(message_edit.is_topic_editable(message), true);

    message.topic = "test topic";
    override(settings_data, "user_can_move_messages_to_another_topic", () => false);
    assert.equal(message_edit.is_topic_editable(message), false);

    page_params.realm_community_topic_editing_limit_seconds = 259200;
    message.timestamp = current_timestamp - 60;

    override(settings_data, "user_can_move_messages_to_another_topic", () => true);
    assert.equal(message_edit.is_topic_editable(message), true);

    message.timestamp = current_timestamp - 600000;
    assert.equal(message_edit.is_topic_editable(message), false);

    page_params.is_moderator = true;
    assert.equal(message_edit.is_topic_editable(message), true);

    page_params.realm_allow_message_editing = false;
    assert.equal(message_edit.is_topic_editable(message), true);
});

run_test("get_deletability", ({override}) => {
    page_params.is_admin = true;
    override(settings_data, "user_can_delete_own_message", () => false);
    page_params.realm_message_content_delete_limit_seconds = null;
    const message = {
        sent_by_me: false,
        locally_echoed: true,
    };

    // Admin can always delete any message
    assert.equal(message_edit.get_deletability(message), true);

    // Non-admin can't delete message sent by others
    page_params.is_admin = false;
    assert.equal(message_edit.get_deletability(message), false);

    // Locally echoed messages are not deletable
    message.sent_by_me = true;
    assert.equal(message_edit.get_deletability(message), false);

    message.locally_echoed = false;
    assert.equal(message_edit.get_deletability(message), false);

    override(settings_data, "user_can_delete_own_message", () => true);
    assert.equal(message_edit.get_deletability(message), true);

    const now = new Date();
    const current_timestamp = now / 1000;
    message.timestamp = current_timestamp - 5;

    page_params.realm_message_content_delete_limit_seconds = 10;
    assert.equal(message_edit.get_deletability(message), true);

    message.timestamp = current_timestamp - 60;
    assert.equal(message_edit.get_deletability(message), false);
});

run_test("stream_and_topic_exist_in_edit_history", () => {
    // A message with no edit history should always return false;
    // the message's current stream_id and topic are not compared
    // to the stream_id and topic parameters.
    const message_no_edits = {
        stream_id: 1,
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
        edit_history: [{prev_content: "content edit to PM"}],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(private_message, 1, "topic match"),
        false,
    );

    // A stream message with only content edits should return false,
    // even if the message's current stream_id and topic are a match.
    const message_content_edit = {
        stream_id: 1,
        topic: "topic match",
        edit_history: [{prev_content: "content edit"}],
    };
    assert.equal(
        message_edit.stream_and_topic_exist_in_edit_history(message_content_edit, 1, "topic match"),
        false,
    );

    const message_stream_edit = {
        stream_id: 6,
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
