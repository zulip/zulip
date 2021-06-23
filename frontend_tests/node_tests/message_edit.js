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
    override(settings_data, "user_can_edit_topic_of_any_message", () => true);
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
            local_id: "25",
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
    page_params.realm_message_content_edit_limit_seconds = 0;
    assert.equal(get_editability(message), editability_types.FULL);

    page_params.realm_message_content_edit_limit_seconds = 10;
    const now = new Date();
    const current_timestamp = now / 1000;
    message.timestamp = current_timestamp - 60;
    // Have 55+10 > 60 seconds from message.timestamp to edit the message; we're good!
    assert.equal(get_editability(message, 55), editability_types.FULL);
    // It's been 60 > 45+10 since message.timestamp. When realm_allow_message_editing
    // is true, we can edit the topic if there is one.
    message.type = "stream";
    assert.equal(get_editability(message, 45), editability_types.TOPIC_ONLY);
    // Right now, we prevent users from editing widgets.
    message.submessages = ["/poll"];
    assert.equal(get_editability(message, 45), editability_types.TOPIC_ONLY);
    delete message.submessages;
    message.type = "private";
    assert.equal(get_editability(message, 45), editability_types.NO_LONGER);
    // If we don't pass a second argument, treat it as 0
    assert.equal(get_editability(message), editability_types.NO_LONGER);

    message = {
        sent_by_me: false,
        type: "stream",
    };
    page_params.realm_edit_topic_policy =
        settings_config.common_message_policy_values.by_everyone.code;
    page_params.realm_allow_message_editing = true;
    page_params.realm_message_content_edit_limit_seconds = 0;
    page_params.realm_community_topic_editing_limit_seconds = 259200;
    page_params.is_admin = false;
    message.timestamp = current_timestamp - 60;
    assert.equal(get_editability(message), editability_types.TOPIC_ONLY);

    // Test `message_edit.is_topic_editable()`
    assert.equal(message_edit.is_topic_editable(message), true);

    message.sent_by_me = true;
    override(settings_data, "user_can_edit_topic_of_any_message", () => false);
    assert.equal(message_edit.is_topic_editable(message), true);

    message.sent_by_me = false;
    assert.equal(message_edit.is_topic_editable(message), false);

    message.sent_by_me = false;
    page_params.is_admin = true;
    assert.equal(message_edit.is_topic_editable(message), true);

    page_params.is_admin = false;
    override(settings_data, "user_can_edit_topic_of_any_message", () => true);
    assert.equal(message_edit.is_topic_editable(message), true);

    message.timestamp = current_timestamp - 600000;
    assert.equal(message_edit.is_topic_editable(message), false);

    page_params.is_moderator = true;
    assert.equal(message_edit.is_topic_editable(message), true);

    page_params.realm_allow_message_editing = false;
    assert.equal(message_edit.is_topic_editable(message), false);
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
