// Dependencies
zrequire('muting');
zrequire('stream_data');

set_global('document', {
    hasFocus: function () {
        return true;
    },
});
set_global('window', {});
set_global('page_params', {
    is_admin: false,
    realm_users: [],
});

zrequire('notifications');

// Not muted streams
var two = {
    subscribed: true,
    name: 'stream_two',
    stream_id: 20,
    in_home_view: true,
};

// Muted streams
var one = {
    subscribed: true,
    name: 'stream_one',
    stream_id: 10,
    in_home_view: false,
};

var three = {
    subscribed: true,
    name: 'stream_three',
    stream_id: 30,
    in_home_view: false,
};

// Add muted topics
muting.add_muted_topic(one.name, 'topic_one');
muting.add_muted_topic(one.name, 'topic_three');
muting.add_muted_topic(three.name, 'topic_five');
muting.add_muted_topic(three.name, 'topic_seven');

// Subscribe to topic
stream_data.add_sub('stream_two', two);

(function test_message_is_notifiable() {
    // This function tests logic for 4 cases
    // that should override any of the user's notifications settings
    // and a 5th that passes it on the user's notifications settings


    // Case 1: If the message was sent by this user,
    //  DO NOT notify the user
        // In this test, all other circumstances should trigger notification
        // EXCEPT sent_by_me, which should trump them
        assert.equal(notifications.message_is_notifiable({
            id: 10,
            content: 'message number 1',
            sent_by_me: true,
            notification_sent: false,
            mentioned_me_directly: true,
            type: 'stream',
            stream: 'stream_two',
            stream_id: 20,
            subject: 'topic_two',
        }), false);

    // Case 2: If the user has already been sent a notificaton about this message,
    //  DO NOT notify the user
        // In this test, all other circumstances should trigger notification
        // EXCEPT notification_sent, which should trump them
        // (ie: it mentions user, it's not muted, etc)
        assert.equal(notifications.message_is_notifiable({
            id: 20,
            content: 'message number 2',
            sent_by_me: false,
            notification_sent: true,
            mentioned_me_directly: true,
            type: 'stream',
            stream: 'stream_two',
            stream_id: 20,
            subject: 'topic_two',
        }), false);

    // Case 3: If a message mentions the user directly,
    //  DO notify the user
        // Mentioning trumps muting
        assert.equal(notifications.message_is_notifiable({
            id: 30,
            content: 'message number three',
            sent_by_me: false,
            notification_sent: false,
            mentioned_me_directly: true,
            type: 'stream',
            stream: 'stream_one',
            stream_id: 10,
            subject: 'topic_three',
        }), true);

        // Mentioning should trigger notification in unmuted topic
        assert.equal(notifications.message_is_notifiable({
            id: 40,
            content: 'message number 4',
            sent_by_me: false,
            notification_sent: false,
            mentioned_me_directly: true,
            type: 'stream',
            stream: 'stream_two',
            stream_id: 20,
            subject: 'topic_two',
        }), true);

    // Case 4: If a message is in a muted stream
    //  and does not mention the user DIRECTLY,
    //  DO NOT notify the user
        assert.equal(notifications.message_is_notifiable({
            id: 50,
            content: 'message number 5',
            sent_by_me: false,
            notification_sent: false,
            mentioned_me_directly: false,
            type: 'stream',
            stream: 'stream_one',
            stream_id: 10,
            subject: 'topic_one',
        }), false);

    // Case 5
        // If none of the above cases apply
        // (ie: topic is not muted, message does not mention user,
        //  no notification sent before, message not sent by user),
        // return true to pass it to notifications settings
        assert.equal(notifications.message_is_notifiable({
            id: 60,
            content: 'message number 6',
            sent_by_me: false,
            notification_sent: false,
            mentioned_me_directly: false,
            type: 'stream',
            stream: 'stream_two',
            stream_id: 20,
            subject: 'topic_two',
        }), true);
}());
