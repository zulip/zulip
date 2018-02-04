set_global('document', null);
set_global('page_params', {});

global.stub_out_jquery();

zrequire('XDate', 'node_modules/xdate/src/xdate');
zrequire('message_edit');

var get_editability = message_edit.get_editability;
var editability_types = message_edit.editability_types;

(function test_get_editability() {
    // You can't edit a null message
    assert.equal(get_editability(null), editability_types.NO);
    // You can't edit a message you didn't send
    assert.equal(get_editability({
        sent_by_me: false,
    }), editability_types.NO);

    // Failed request are currently not editable (though we want to
    // change this back).
    assert.equal(get_editability({
        sent_by_me: true,
        failed_request: true,
    }), editability_types.NO);

    // Locally echoed messages are not editable, since the message hasn't
    // finished being sent yet.
    assert.equal(get_editability({
        sent_by_me: true,
        local_id: 25,
    }), editability_types.NO);

    // For the rest of these tests, we only consider messages sent by the
    // user, and that were successfully sent (i.e. no failed_request or local_id)
    var message = {
        sent_by_me: true,
    };

    global.page_params = {
        realm_allow_message_editing: false,
    };
    assert.equal(get_editability(message), editability_types.NO);

    global.page_params = {
        realm_allow_message_editing: true,
        // Limit of 0 means no time limit on editing messages
        realm_message_content_edit_limit_seconds: 0,
    };
    assert.equal(get_editability(message), editability_types.FULL);

    global.page_params = {
        realm_allow_message_editing: true,
        realm_message_content_edit_limit_seconds: 10,
    };
    var now = new Date();
    var current_timestamp = now/1000;
    message.timestamp = current_timestamp - 60;
    // Have 55+10 > 60 seconds from message.timestamp to edit the message; we're good!
    assert.equal(get_editability(message, 55), editability_types.FULL);
    // It's been 60 > 45+10 since message.timestamp. When realm_allow_message_editing
    // is true, we can edit the topic if there is one.
    message.type = 'stream';
    assert.equal(get_editability(message, 45), editability_types.TOPIC_ONLY);
    message.type = 'private';
    assert.equal(get_editability(message, 45), editability_types.NO_LONGER);
    // If we don't pass a second argument, treat it as 0
    assert.equal(get_editability(message), editability_types.NO_LONGER);
}());
