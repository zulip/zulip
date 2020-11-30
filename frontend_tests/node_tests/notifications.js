"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {make_zjquery} = require("../zjsunit/zjquery");

// Dependencies
set_global(
    "$",
    make_zjquery({
        silent: true,
    }),
);
set_global("document", {
    hasFocus() {
        return true;
    },
});
set_global("page_params", {
    is_admin: false,
    realm_users: [],
    enable_desktop_notifications: true,
    enable_sounds: true,
    wildcard_mentions_notify: true,
});
const _navigator = {
    userAgent: "Mozilla/5.0 AppleWebKit/537.36 Chrome/64.0.3282.167 Safari/537.36",
};
set_global("navigator", _navigator);

zrequire("alert_words");
zrequire("muting");
zrequire("stream_data");
zrequire("people");
zrequire("ui");
zrequire("spoilers");
spoilers.hide_spoilers_in_notification = () => {};

rewiremock.proxy(() => zrequire("notifications"), {
    "../../static/js/favicon": {},
});

// Not muted streams
const general = {
    subscribed: true,
    name: "general",
    stream_id: 10,
    is_muted: false,
    wildcard_mentions_notify: null,
};

// Muted streams
const muted = {
    subscribed: true,
    name: "muted",
    stream_id: 20,
    is_muted: true,
    wildcard_mentions_notify: null,
};

stream_data.add_sub(general);
stream_data.add_sub(muted);

muting.add_muted_topic(general.stream_id, "muted topic");

run_test("message_is_notifiable", () => {
    // A notification is sent if both message_is_notifiable(message)
    // and the appropriate should_send_*_notification function return
    // true.

    // Case 1: If the message was sent by this user,
    //  DO NOT notify the user
    // In this test, all other circumstances should trigger notification
    // EXCEPT sent_by_me, which should trump them
    let message = {
        id: muted.stream_id,
        content: "message number 1",
        sent_by_me: true,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream: "general",
        stream_id: general.stream_id,
        topic: "whatever",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    // Not notifiable because it was sent by the current user
    assert.equal(notifications.message_is_notifiable(message), false);

    // Case 2: If the user has already been sent a notification about this message,
    //  DO NOT notify the user
    // In this test, all other circumstances should trigger notification
    // EXCEPT notification_sent, which should trump them
    // (ie: it mentions user, it's not muted, etc)
    message = {
        id: general.stream_id,
        content: "message number 2",
        sent_by_me: false,
        notification_sent: true,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream: "general",
        stream_id: general.stream_id,
        topic: "whatever",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), false);

    // Case 3: If a message mentions the user directly,
    //  DO notify the user
    // Mentioning trumps muting
    message = {
        id: 30,
        content: "message number 3",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream: "muted",
        stream_id: muted.stream_id,
        topic: "topic_three",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), true);

    // Case 4:
    // Mentioning should trigger notification in unmuted topic
    message = {
        id: 40,
        content: "message number 4",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream: "general",
        stream_id: general.stream_id,
        topic: "vanilla",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), true);

    // Case 5:
    // Wildcard mention should trigger notification in unmuted topic
    // if wildcard_mentions_notify
    message = {
        id: 40,
        content: "message number 4",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: false,
        type: "stream",
        stream: "general",
        stream_id: general.stream_id,
        topic: "vanilla",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), true);

    // But not if it's disabled
    page_params.wildcard_mentions_notify = false;
    assert.equal(notifications.should_send_desktop_notification(message), false);
    assert.equal(notifications.should_send_audible_notification(message), false);
    assert.equal(notifications.message_is_notifiable(message), true);

    // And the stream-level setting overrides the global setting
    general.wildcard_mentions_notify = true;
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), true);

    // Reset state
    page_params.wildcard_mentions_notify = true;
    general.wildcard_mentions_notify = null;

    // Case 6: If a message is in a muted stream
    //  and does not mention the user DIRECTLY (i.e. wildcard mention),
    //  DO NOT notify the user
    message = {
        id: 50,
        content: "message number 5",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: false,
        type: "stream",
        stream: "muted",
        stream_id: muted.stream_id,
        topic: "whatever",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), false);

    // Case 7: If a message is in a muted stream
    //  and does mention the user DIRECTLY,
    //  DO notify the user
    message = {
        id: 50,
        content: "message number 5",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream: "muted",
        stream_id: muted.stream_id,
        topic: "whatever",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), true);

    // Case 8: If a message is in a muted topic
    //  and does not mention the user DIRECTLY (i.e. wildcard mention),
    //  DO NOT notify the user
    message = {
        id: 50,
        content: "message number 6",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: false,
        type: "stream",
        stream: "general",
        stream_id: general.stream_id,
        topic: "muted topic",
    };
    assert.equal(notifications.should_send_desktop_notification(message), true);
    assert.equal(notifications.should_send_audible_notification(message), true);
    assert.equal(notifications.message_is_notifiable(message), false);

    // If none of the above cases apply
    // (ie: topic is not muted, message does not mention user,
    //  no notification sent before, message not sent by user),
    // return true to pass it to notifications settings, which will return false.
    message = {
        id: 60,
        content: "message number 7",
        sent_by_me: false,
        notification_sent: false,
        mentioned: false,
        mentioned_me_directly: false,
        type: "stream",
        stream: "general",
        stream_id: general.stream_id,
        topic: "whatever",
    };
    assert.equal(notifications.should_send_desktop_notification(message), false);
    assert.equal(notifications.should_send_audible_notification(message), false);
    assert.equal(notifications.message_is_notifiable(message), true);
});

run_test("basic_notifications", () => {
    let n; // Object for storing all notification data for assertions.
    let last_closed_message_id = null;
    let last_shown_message_id = null;

    // Notifications API stub
    class StubNotification {
        constructor(title, {icon, body, tag}) {
            this.icon = icon;
            this.body = body;
            this.tag = tag;
            // properties for testing.
            this.tests = {
                shown: false,
            };
            last_shown_message_id = this.tag;
        }

        addEventListener() {}

        close() {
            last_closed_message_id = this.tag;
        }
    }

    notifications.set_notification_api(StubNotification);

    const message_1 = {
        id: 1000,
        content: "@-mentions the user",
        avatar_url: "url",
        sent_by_me: false,
        sender_full_name: "Jesse Pinkman",
        notification_sent: false,
        mentioned_me_directly: true,
        type: "stream",
        stream: "general",
        stream_id: muted.stream_id,
        topic: "whatever",
    };

    const message_2 = {
        id: 1500,
        avatar_url: "url",
        content: "@-mentions the user",
        sent_by_me: false,
        sender_full_name: "Gus Fring",
        notification_sent: false,
        mentioned_me_directly: true,
        type: "stream",
        stream: "general",
        stream_id: muted.stream_id,
        topic: "lunch",
    };

    // Send notification.
    notifications.process_notification({message: message_1, desktop_notify: true});
    n = notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Remove notification.
    notifications.close_notification(message_1);
    n = notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, message_1.id);

    // Send notification.
    message_1.id = 1001;
    notifications.process_notification({message: message_1, desktop_notify: true});
    n = notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Process same message again. Notification count shouldn't increase.
    message_1.id = 1002;
    notifications.process_notification({message: message_1, desktop_notify: true});
    n = notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id);

    // Send another message. Notification count should increase.
    notifications.process_notification({message: message_2, desktop_notify: true});
    n = notifications.get_notifications();
    assert.equal(n.has("Gus Fring to general > lunch"), true);
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 2);
    assert.equal(last_shown_message_id, message_2.id);

    // Remove notifications.
    notifications.close_notification(message_1);
    notifications.close_notification(message_2);
    n = notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, message_2.id);
});
