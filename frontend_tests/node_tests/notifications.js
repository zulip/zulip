// Dependencies
set_global('$', global.make_zjquery({
    silent: true,
}));
set_global('blueslip', global.make_zblueslip());
set_global('document', {
    hasFocus: function () {
        return true;
    },
});
set_global('page_params', {
    is_admin: false,
    realm_users: [],
});

zrequire('muting');
zrequire('stream_data');
zrequire('people');
zrequire('ui');
zrequire('util');

zrequire('notifications');

// Not muted streams
var general = {
    subscribed: true,
    name: 'general',
    stream_id: 10,
    in_home_view: true,
};

// Muted streams
var muted = {
    subscribed: true,
    name: 'muted',
    stream_id: 20,
    in_home_view: false,
};

stream_data.add_sub('general', general);
stream_data.add_sub('muted', muted);

muting.add_muted_topic(general.stream_id, 'muted topic');

run_test('message_is_notifiable', () => {
    // Case 1: If the message was sent by this user,
    //  DO NOT notify the user
    // In this test, all other circumstances should trigger notification
    // EXCEPT sent_by_me, which should trump them
    assert.equal(notifications.message_is_notifiable({
        id: muted.stream_id,
        content: 'message number 1',
        sent_by_me: true,
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'general',
        stream_id: general.stream_id,
        topic: 'whatever',
    }), false);

    // Case 2: If the user has already been sent a notificaton about this message,
    //  DO NOT notify the user
    // In this test, all other circumstances should trigger notification
    // EXCEPT notification_sent, which should trump them
    // (ie: it mentions user, it's not muted, etc)
    assert.equal(notifications.message_is_notifiable({
        id: general.stream_id,
        content: 'message number 2',
        sent_by_me: false,
        notification_sent: true,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'general',
        stream_id: general.stream_id,
        topic: 'whatever',
    }), false);

    // Case 3: If a message mentions the user directly,
    //  DO notify the user
    // Mentioning trumps muting
    assert.equal(notifications.message_is_notifiable({
        id: 30,
        content: 'message number 3',
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'muted',
        stream_id: muted.stream_id,
        topic: 'topic_three',
    }), true);

    // Case 4:
    // Mentioning should trigger notification in unmuted topic
    assert.equal(notifications.message_is_notifiable({
        id: 40,
        content: 'message number 4',
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'general',
        stream_id: general.stream_id,
        topic: 'vanilla',
    }), true);

    // Case 5: If a message is in a muted stream
    //  and does not mention the user DIRECTLY,
    //  DO NOT notify the user
    assert.equal(notifications.message_is_notifiable({
        id: 50,
        content: 'message number 5',
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: false,
        type: 'stream',
        stream: 'muted',
        stream_id: muted.stream_id,
        topic: 'whatever',
    }), false);

    // Case 6: If a message is in a muted topic
    //  and does not mention the user DIRECTLY,
    //  DO NOT notify the user
    assert.equal(notifications.message_is_notifiable({
        id: 50,
        content: 'message number 6',
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: false,
        type: 'stream',
        stream: 'general',
        stream_id: general.stream_id,
        topic: 'muted topic',
    }), false);

    // Case 7
    // If none of the above cases apply
    // (ie: topic is not muted, message does not mention user,
    //  no notification sent before, message not sent by user),
    // return true to pass it to notifications settings
    assert.equal(notifications.message_is_notifiable({
        id: 60,
        content: 'message number 7',
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: false,
        type: 'stream',
        stream: 'general',
        stream_id: general.stream_id,
        topic: 'whatever',
    }), true);
});


run_test('basic_notifications', () => {

    var n; // Object for storing all notification data for assertions.
    var last_closed_message_id = null;
    var last_shown_message_id = null;

    // Notifications API stub
    notifications.set_notification_api({
        createNotification: function createNotification(icon, title, content, tag) {
            var notification_object = {icon: icon, body: content, tag: tag};
            // properties for testing.
            notification_object.tests = {
                shown: false,
            };
            notification_object.show = function () {
                last_shown_message_id = this.tag;
            };
            notification_object.close = function () {
                last_closed_message_id = this.tag;
            };
            notification_object.cancel = function () { notification_object.close(); };
            return notification_object;
        },
    });

    var message_1 = {
        id: 1000,
        content: '@-mentions the user',
        avatar_url: 'url',
        sent_by_me: false,
        sender_full_name: 'Jesse Pinkman',
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'general',
        stream_id: muted.stream_id,
        topic: 'whatever',
    };

    var message_2 = {
        id: 1500,
        avatar_url: 'url',
        content: '@-mentions the user',
        sent_by_me: false,
        sender_full_name: 'Gus Fring',
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'general',
        stream_id: muted.stream_id,
        topic: 'lunch',
    };

    // Send notification.
    notifications.process_notification({message: message_1, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('Jesse Pinkman to general > whatever' in n, true);
    assert.equal(Object.keys(n).length, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Remove notification.
    notifications.close_notification(message_1);
    n = notifications.get_notifications();
    assert.equal('Jesse Pinkman to general > whatever' in n, false);
    assert.equal(Object.keys(n).length, 0);
    assert.equal(last_closed_message_id, message_1.id);

    // Send notification.
    message_1.id = 1001;
    notifications.process_notification({message: message_1, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('Jesse Pinkman to general > whatever' in n, true);
    assert.equal(Object.keys(n).length, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Process same message again. Notification count shouldn't increase.
    message_1.id = 1002;
    notifications.process_notification({message: message_1, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('Jesse Pinkman to general > whatever' in n, true);
    assert.equal(Object.keys(n).length, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Send another message. Notification count should increase.
    notifications.process_notification({message: message_2, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('Gus Fring to general > lunch' in n, true);
    assert.equal('Jesse Pinkman to general > whatever' in n, true);
    assert.equal(Object.keys(n).length, 2);
    assert.equal(last_shown_message_id, message_2.id);

    // Remove notifications.
    notifications.close_notification(message_1);
    notifications.close_notification(message_2);
    n = notifications.get_notifications();
    assert.equal('Jesse Pinkman to general > whatever' in n, false);
    assert.equal(Object.keys(n).length, 0);
    assert.equal(last_closed_message_id, message_2.id);
});
