// Dependencies
set_global('$', global.make_zjquery({
    silent: true,
}));
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
// For people.js
set_global('md5', function (s) {
    return 'md5-' + s;
});

zrequire('muting');
zrequire('stream_data');
zrequire('ui');
zrequire('people');

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


(function test_basic_notifications() {

    var n; // Object for storing all notification data for assertions.
    var last_closed_message_id = null;
    var last_shown_message_id = null;

    // Notifications API stub
    notifications.set_notification_api({
        checkPermission: function checkPermission() {
            if (window.Notification.permission === 'granted') {
                return 0;
            }
            return 2;
        },
        requestPermission: function () {
            return;
        },
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
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'stream_one',
        stream_id: 10,
        subject: 'topic_two',
    };

    var message_2 = {
        id: 1500,
        content: '@-mentions the user',
        sent_by_me: false,
        notification_sent: false,
        mentioned_me_directly: true,
        type: 'stream',
        stream: 'stream_one',
        stream_id: 10,
        subject: 'topic_four',
    };

    // Send notification.
    notifications.process_notification({message: message_1, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('undefined to stream_one > topic_two' in n, true);
    assert.equal(Object.keys(n).length, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Remove notification.
    notifications.close_notification(message_1);
    n = notifications.get_notifications();
    assert.equal('undefined to stream_one > topic_two' in n, false);
    assert.equal(Object.keys(n).length, 0);
    assert.equal(last_closed_message_id, message_1.id);

    // Send notification.
    message_1.id = 1001;
    notifications.process_notification({message: message_1, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('undefined to stream_one > topic_two' in n, true);
    assert.equal(Object.keys(n).length, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Process same message again. Notification count shouldn't increase.
    message_1.id = 1002;
    notifications.process_notification({message: message_1, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('undefined to stream_one > topic_two' in n, true);
    assert.equal(Object.keys(n).length, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Send another message. Notification count should increase.
    notifications.process_notification({message: message_2, webkit_notify: true});
    n = notifications.get_notifications();
    assert.equal('undefined to stream_one > topic_four' in n, true);
    assert.equal(Object.keys(n).length, 2);
    assert.equal(last_shown_message_id, message_2.id);

    // Remove notifications.
    notifications.close_notification(message_1);
    notifications.close_notification(message_2);
    n = notifications.get_notifications();
    assert.equal('undefined to stream_one > topic_two' in n, false);
    assert.equal(Object.keys(n).length, 0);
    assert.equal(last_closed_message_id, message_2.id);
}());
