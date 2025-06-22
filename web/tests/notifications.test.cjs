"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {$} = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/electron_bridge");
mock_esm("../src/spoilers", {hide_spoilers_in_notification() {}});
const channel = mock_esm("../src/channel");
const unread_ops = mock_esm("../src/unread_ops", {
    is_window_focused: () => false,
});

const user_topics = zrequire("user_topics");
const stream_data = zrequire("stream_data");
const people = zrequire("people");

const desktop_notifications = zrequire("desktop_notifications");
const message_helper = zrequire("message_helper");
const message_notifications = zrequire("message_notifications");
const muted_users = zrequire("muted_users");
const emoji = zrequire("emoji");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");
const reaction_notifications = zrequire("reaction_notifications");

function received_reaction(event) {
    reaction_notifications.received_reactions([{...event, op: "add"}]);
}

function removed_reaction(event) {
    reaction_notifications.received_reactions([{...event, op: "remove"}]);
}

const realm = {};
set_realm(realm);
const current_user = {user_id: 1};
set_current_user(current_user);
const user_settings = {};
initialize_user_settings({user_settings});

// Not muted streams
const general = make_stream({
    subscribed: true,
    name: "general",
    stream_id: 10,
    is_muted: false,
    wildcard_mentions_notify: null,
});

// Muted streams
const muted = make_stream({
    subscribed: true,
    name: "muted",
    stream_id: 20,
    is_muted: true,
    wildcard_mentions_notify: null,
});

stream_data.add_sub_for_tests(general);
stream_data.add_sub_for_tests(muted);

user_topics.update_user_topics(
    general.stream_id,
    general.name,
    "muted topic",
    user_topics.all_visibility_policies.MUTED,
);

user_topics.update_user_topics(
    general.stream_id,
    general.name,
    "unmuted topic",
    user_topics.all_visibility_policies.UNMUTED,
);

user_topics.update_user_topics(
    general.stream_id,
    general.name,
    "followed topic",
    user_topics.all_visibility_policies.FOLLOWED,
);

user_topics.update_user_topics(
    muted.stream_id,
    muted.name,
    "unmuted topic",
    user_topics.all_visibility_policies.UNMUTED,
);

user_topics.update_user_topics(
    muted.stream_id,
    muted.name,
    "inherit visibility topic",
    user_topics.all_visibility_policies.INHERIT,
);

function test(label, f) {
    run_test(label, (helpers) => {
        helpers.override(current_user, "is_admin", false);
        page_params.realm_users = [];
        helpers.override(user_settings, "enable_followed_topic_desktop_notifications", true);
        helpers.override(user_settings, "enable_followed_topic_audible_notifications", true);
        helpers.override(user_settings, "enable_desktop_notifications", true);
        helpers.override(user_settings, "enable_sounds", true);
        helpers.override(user_settings, "enable_followed_topic_wildcard_mentions_notify", true);
        helpers.override(user_settings, "wildcard_mentions_notify", true);
        helpers.override(user_settings, "notification_sound", "ding");
        f(helpers);
    });
}

test("message_is_notifiable", ({override}) => {
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
        stream_id: general.stream_id,
        topic: "whatever",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    // Not notifiable because it was sent by the current user
    assert.equal(message_notifications.message_is_notifiable(message), false);

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
        stream_id: general.stream_id,
        topic: "whatever",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), false);

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
        stream_id: muted.stream_id,
        topic: "topic_three",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Case 4: If the message has been sent to a followed topic,
    // DO visually and audibly notify the user if 'enable_followed_topic_desktop_notifications'
    // and 'enable_followed_topic_audible_notifications' are enabled, respectively.
    // Messages to followed topics trumps muting
    message = {
        id: 30,
        content: "message number 3",
        sent_by_me: false,
        notification_sent: false,
        mentioned: false,
        mentioned_me_directly: false,
        type: "stream",
        stream_id: general.stream_id,
        topic: "followed topic",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // But not if 'enable_followed_topic_desktop_notifications'
    // and 'enable_followed_topic_audible_notifications' are disabled.
    override(user_settings, "enable_followed_topic_desktop_notifications", false);
    override(user_settings, "enable_followed_topic_audible_notifications", false);
    assert.equal(message_notifications.should_send_desktop_notification(message), false);
    assert.equal(message_notifications.should_send_audible_notification(message), false);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Reset state
    override(user_settings, "enable_followed_topic_desktop_notifications", true);

    // Case 5:
    // Mentioning should trigger notification in unmuted topic
    message = {
        id: 40,
        content: "message number 4",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream_id: general.stream_id,
        topic: "vanilla",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Case 6:
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
        stream_id: general.stream_id,
        topic: "vanilla",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // But not if it's disabled
    override(user_settings, "wildcard_mentions_notify", false);
    assert.equal(message_notifications.should_send_desktop_notification(message), false);
    assert.equal(message_notifications.should_send_audible_notification(message), false);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // And the stream-level setting overrides the global setting
    general.wildcard_mentions_notify = true;
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Reset state
    override(user_settings, "wildcard_mentions_notify", true);
    general.wildcard_mentions_notify = null;

    // Case 7: If a message is in a muted stream
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
        stream_id: muted.stream_id,
        topic: "whatever",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), false);

    // Case 8: If a message is in a muted stream
    //  and has a wildcard mention with channel-specific wildcard_mentions_notify=true,
    //  DO notify the user (channel-specific setting overrides channel muting)
    muted.wildcard_mentions_notify = true;
    message = {
        id: 50,
        content: "message number 5a",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: false,
        type: "stream",
        stream_id: muted.stream_id,
        topic: "whatever",
    };
    assert.equal(message_notifications.message_is_notifiable(message), true);
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);

    // Reset state
    muted.wildcard_mentions_notify = null;

    // Case 9: If a message is in a muted stream
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
        stream_id: muted.stream_id,
        topic: "whatever",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Case 10: If a message is in a muted topic
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
        stream_id: general.stream_id,
        topic: "muted topic",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), false);

    // Case 11:
    // For wildcard mentions, even with channel-specific
    // wildcard_mentions_notify=True, muted topics suppress notifications.
    message = {
        id: 50,
        content: "message number 6",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: false,
        type: "stream",
        stream_id: general.stream_id,
        topic: "muted topic",
    };
    assert.equal(message_notifications.message_is_notifiable(message), false);
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);

    // Case 12:
    // Wildcard mentions in a followed topic with 'wildcard_mentions_notify',
    // 'enable_followed_topic_desktop_notifications',
    // 'enable_followed_topic_audible_notifications' disabled and
    // 'enable_followed_topic_wildcard_mentions_notify' enabled;
    // DO visually and audibly notify the user
    override(user_settings, "wildcard_mentions_notify", false);
    override(user_settings, "enable_followed_topic_desktop_notifications", false);
    override(user_settings, "enable_followed_topic_audible_notifications", false);
    message = {
        id: 50,
        content: "message number 5",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: false,
        type: "stream",
        stream_id: general.stream_id,
        topic: "followed topic",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), true);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // But not if 'enable_followed_topic_wildcard_mentions_notify' is disabled
    override(user_settings, "enable_followed_topic_wildcard_mentions_notify", false);
    assert.equal(message_notifications.should_send_desktop_notification(message), false);
    assert.equal(message_notifications.should_send_audible_notification(message), false);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Reset state
    override(user_settings, "wildcard_mentions_notify", true);
    override(user_settings, "enable_followed_topic_desktop_notifications", true);
    override(user_settings, "enable_followed_topic_audible_notifications", true);
    override(user_settings, "enable_followed_topic_wildcard_mentions_notify", true);

    // Case 13: If `None` is selected as the notification sound, send no
    // audible notification, no matter what other user configurations are.
    message = {
        id: 50,
        content: "message number 7",
        sent_by_me: false,
        notification_sent: false,
        mentioned: true,
        mentioned_me_directly: true,
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
    };
    override(user_settings, "notification_sound", "none");
    assert.equal(message_notifications.should_send_desktop_notification(message), true);
    assert.equal(message_notifications.should_send_audible_notification(message), false);
    assert.equal(message_notifications.message_is_notifiable(message), true);

    // Reset state
    override(user_settings, "notification_sound", "ding");

    // If none of the above cases apply
    // (ie: topic is not muted, message does not mention user,
    //  no notification sent before, message not sent by user),
    // return true to pass it to notifications settings, which will return false.
    message = {
        id: 60,
        content: "message number 8",
        sent_by_me: false,
        notification_sent: false,
        mentioned: false,
        mentioned_me_directly: false,
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
    };
    assert.equal(message_notifications.should_send_desktop_notification(message), false);
    assert.equal(message_notifications.should_send_audible_notification(message), false);
    assert.equal(message_notifications.message_is_notifiable(message), true);
});

test("reaction_is_notifiable", () => {
    const my_user_id = 1;
    const other_user_id = 3;
    const muted_user_id = 5;
    muted_users.add_muted_user(muted_user_id);
    // Case 1: Not notifiable since reaction is from current user
    let message = {
        id: 1,
        type: "private",
        content: "Reaction to DM",
        sender_id: "1",
        to_user_ids: "31",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, my_user_id), false);

    // Case 2: Reaction to someone else's message should not notify
    message = {
        id: 2,
        content: "Reaction to someone else's message",
        type: "stream",
        stream_id: general.stream_id,
        sender_id: "2",
        topic: "followed topic",
        sent_by_me: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), false);

    // Case 3: Reaction from muted user should not notify
    message = {
        id: 3,
        content: "Muted user reacts to my message",
        type: "stream",
        stream_id: general.stream_id,
        sender_id: "1",
        topic: "followed topic",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, muted_user_id), false);

    // Case 4: Reaction to muted stream message should not notify
    message = {
        id: 4,
        content: "Reaction to my muted stream message",
        type: "stream",
        stream_id: muted.stream_id,
        topic: "inherit visibility topic",
        sender_id: "1",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), false);

    // Case 5: Reaction to muted stream message but topic is unmuted
    message = {
        id: 5,
        content: "Reaction to my muted stream but unmuted topic message",
        type: "stream",
        stream_id: muted.stream_id,
        topic: "unmuted topic",
        sender_id: "1",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), true);

    // Case 6: Reaction to unmuted stream but muted topic message should not notify
    message = {
        id: 6,
        content: "Reaction to my muted topic message",
        type: "stream",
        stream_id: general.stream_id,
        topic: "muted topic",
        sender_id: "1",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), false);

    // Reaction to DM messages
    message = {
        id: 7,
        type: "private",
        content: "Reaction to my DM",
        sender_id: "1",
        to_user_ids: "31",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), true);

    // Reaction to followed topic message
    message = {
        id: 8,
        content: "Reaction to my followed topic message",
        type: "stream",
        stream_id: general.stream_id,
        sender_id: "1",
        topic: "followed topic",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), true);

    // Reaction to unmuted topic message
    message = {
        id: 9,
        content: "Reaction to my unmuted topic message",
        type: "stream",
        stream_id: general.stream_id,
        sender_id: "1",
        topic: "whatever",
        sent_by_me: true,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message, other_user_id), true);
});

test("basic_notifications", () => {
    const $emoji_stub = $.create("emoji-stub");
    $emoji_stub.set_matches("img", false);
    $emoji_stub.set_contents([]);
    const $katex_stub = $.set_results("katex-stub", []);
    $("<div>").set_find_results(".emoji", $emoji_stub);
    $("<div>").set_find_results("span.katex", $katex_stub);
    $("<div>").set_children([]);

    let n; // Object for storing all notification data for assertions.
    let last_closed_message_id = null;
    let last_shown_message_id = null;
    let last_shown_title = null;
    // Counts how many notifications have been shown, so tests can verify
    // that an operation does (or does not) pop up a new notification.
    let shown_count = 0;

    // Notifications API stub
    class StubNotification {
        constructor(title, {icon, body, tag}) {
            this.title = title;
            this.icon = icon;
            this.body = body;
            this.tag = tag;
            // properties for testing.
            this.tests = {
                shown: false,
            };
            last_shown_message_id = this.tag;
            last_shown_title = title;
            shown_count += 1;
        }

        addEventListener() {}

        close() {
            last_closed_message_id = this.tag;
        }
    }

    desktop_notifications.set_notification_api(StubNotification);

    const jesse = make_user({
        email: "jesse@example.com",
        full_name: "Jesse Pinkman",
        user_id: 1,
    });
    const gus = make_user({
        email: "gus@example.com",
        full_name: "Gus Fring",
        user_id: 2,
    });
    const walter = make_user({
        email: "walter@example.com",
        full_name: "Walter White",
        user_id: 3,
    });
    people.add_active_user(jesse);
    people.add_active_user(gus);
    people.add_active_user(walter);

    const stream_message_1 = {
        id: 1000,
        content: "@-mentions the user",
        avatar_url: "url",
        sent_by_me: false,
        sender_id: jesse.user_id,
        sender_full_name: jesse.full_name,
        notification_sent: false,
        mentioned_me_directly: true,
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
    };

    const stream_message_2 = {
        id: 1500,
        avatar_url: "url",
        content: "@-mentions the user",
        sent_by_me: false,
        sender_id: gus.user_id,
        sender_full_name: gus.full_name,
        notification_sent: false,
        mentioned_me_directly: true,
        type: "stream",
        stream_id: general.stream_id,
        topic: "lunch",
    };

    const direct_message = {
        id: 2000,
        content: "direct message",
        avatar_url: "url",
        sent_by_me: false,
        sender_id: gus.user_id,
        sender_full_name: gus.full_name,
        notification_sent: false,
        type: "private",
        to_user_ids: `${gus.user_id},${walter.user_id}`,
        display_recipient: [
            {id: gus.user_id, full_name: gus.full_name, email: gus.email},
            {id: walter.user_id, full_name: walter.full_name, email: walter.email},
        ],
        display_reply_to: `${gus.full_name}, ${walter.full_name}`,
    };

    const test_notification_message = {
        id: 3000,
        type: "test-notification",
        sender_email: "notification-bot@zulip.com",
        sender_full_name: "Notification Bot",
        display_reply_to: "Notification Bot",
        content: "test notification",
        unread: true,
    };

    // Send notification.
    message_notifications.process_notification({message: stream_message_1, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("channel:1:10:whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());

    // Remove notification.
    desktop_notifications.close_notification(stream_message_1.id);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("channel:1:10:whatever"), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, stream_message_1.id.toString());

    // Send notification.
    stream_message_1.id = 1001;
    message_notifications.process_notification({message: stream_message_1, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("channel:1:10:whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());

    // Process same message again. Notification count shouldn't increase.
    stream_message_1.id = 1002;
    message_notifications.process_notification({message: stream_message_1, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("channel:1:10:whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());

    // Send another message. Notification count should increase.
    message_notifications.process_notification({message: stream_message_2, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("channel:2:10:lunch"), true);
    assert.equal(n.has("channel:1:10:whatever"), true);
    assert.equal(n.size, 2);
    assert.equal(last_shown_message_id, stream_message_2.id.toString());

    // Remove notifications.
    desktop_notifications.close_notification(stream_message_1.id);
    desktop_notifications.close_notification(stream_message_2.id);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("channel:1:10:whatever"), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, stream_message_2.id.toString());

    message_notifications.process_notification({message: direct_message, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("dm:2,3"), true);
    assert.equal(n.size, 1);
    desktop_notifications.close_notification(direct_message.id);

    message_notifications.process_notification({
        message: test_notification_message,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("test:Notification Bot"), true);
    assert.equal(n.size, 1);
    desktop_notifications.close_notification(test_notification_message.id);

    // Reaction notifications
    const alice = {
        email: "alice@zulip.com",
        user_id: 1,
        full_name: "Alice Smith",
    };
    const fred = {
        email: "fred@zulip.com",
        user_id: 2,
        full_name: "Fred Flintstone",
    };
    const jill = {
        email: "jill@zulip.com",
        user_id: 3,
        full_name: "Jill Hill",
    };

    people.add_active_user(alice);
    people.add_active_user(fred);
    people.add_active_user(jill);

    const emoji_tada = {
        name: "tada",
        aliases: ["tada"],
        emoji_url: "TBD",
        emoji_code: "1f389",
    };
    const emoji_thumbs_up = {
        name: "thumbs_up",
        aliases: ["thumbs_up"],
        emoji_url: "TBD",
        emoji_code: "1f44d",
    };
    const emoji_heart = {
        name: "heart",
        aliases: ["heart"],
        emoji_url: "TBD",
        emoji_code: "2764",
    };

    const emojis_by_name = new Map(
        Object.entries({
            tada: emoji_tada,
            thumbs_up: emoji_thumbs_up,
            heart: emoji_heart,
        }),
    );

    const name_to_codepoint = Object.fromEntries(
        emojis_by_name.entries().map(([key, val]) => [key, val.emoji_code]),
    );

    const codepoint_to_name = Object.fromEntries(
        emojis_by_name.entries().map(([key, val]) => [val.emoji_code, key]),
    );

    const emoji_codes = {
        name_to_codepoint,
        names: emojis_by_name.keys().toArray(),
        emoji_catalog: {},
        emoticon_conversions: {},
        codepoint_to_name,
    };

    emoji.initialize({
        realm_emoji: {},
        emoji_codes,
    });

    emoji.active_realm_emojis.clear();
    emoji.emojis_by_name.clear();

    for (const [key, val] of emojis_by_name) {
        emoji.emojis_by_name.set(key, val);
    }

    // A reaction event's message_id always matches the message it is
    // for, since received_reactions looks the message up by that id.
    const reaction_1 = {
        message_id: stream_message_1.id,
        user_id: alice.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_tada.name,
        emoji_code: emoji_tada.emoji_code,
    };
    const reaction_2 = {
        message_id: stream_message_1.id,
        user_id: jill.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_tada.name,
        emoji_code: emoji_tada.emoji_code,
    };
    const reaction_3 = {
        message_id: stream_message_1.id,
        user_id: fred.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_heart.name,
        emoji_code: emoji_heart.emoji_code,
    };

    const reaction_4 = {
        message_id: stream_message_2.id,
        user_id: alice.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_tada.name,
        emoji_code: emoji_tada.emoji_code,
    };

    // With desktop_notify false (e.g. browser permission not granted), no
    // desktop notification is shown.
    reaction_notifications.process_notification({
        message: stream_message_1,
        reaction_event: reaction_1,
        desktop_notify: false,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), false);

    // Incoming reaction event should notify user
    reaction_notifications.process_notification({
        message: stream_message_1,
        reaction_event: reaction_1,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());
    // Unicode emoji are rendered as the glyph itself in the title.
    assert.equal(last_shown_title, "translated: Alice Smith reacted with 🎉");

    // Reaction to same message shouldn't increase notification obj
    reaction_notifications.process_notification({
        message: stream_message_1,
        reaction_event: reaction_2,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());

    // Send another reaction to same message
    reaction_notifications.process_notification({
        message: stream_message_1,
        reaction_event: reaction_3,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());

    // Reaction to another message should increase notification obj
    reaction_notifications.process_notification({
        message: stream_message_2,
        reaction_event: reaction_4,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_2.id.toString()), true);
    assert.equal(n.size, 2);
    assert.equal(last_shown_message_id, stream_message_2.id.toString());

    // A reaction with a realm emoji that is no longer active (e.g. a
    // deactivated custom emoji, whose name is absent from
    // `emoji.emojis_by_name` but can still receive new votes) is rendered
    // as `:emoji_name:`.
    const deactivated_realm_emoji_reaction = {
        message_id: stream_message_1.id,
        user_id: jill.user_id,
        reaction_type: "realm_emoji",
        emoji_name: "deactivated_custom",
        emoji_code: "1234",
    };
    reaction_notifications.process_notification({
        message: stream_message_1,
        reaction_event: deactivated_realm_emoji_reaction,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 2);
    assert.equal(last_shown_message_id, stream_message_1.id.toString());
    assert.ok(last_shown_title.includes(":deactivated_custom:"));

    // A unicode reaction whose emoji_code is not a valid codepoint cannot
    // be rendered as a glyph. That should never reach a client, so it is
    // logged, and the title falls back to `:emoji_name:` rather than
    // showing the user a placeholder that names no emoji at all.
    blueslip.expect("error", "Invalid unicode codepoint for emoji");
    reaction_notifications.process_notification({
        message: stream_message_1,
        reaction_event: {
            message_id: stream_message_1.id,
            user_id: jill.user_id,
            reaction_type: "unicode_emoji",
            emoji_name: "bogus",
            emoji_code: "not-a-codepoint",
        },
        desktop_notify: true,
    });
    assert.ok(last_shown_title.includes(":bogus:"));
    assert.ok(!last_shown_title.includes("invalid_emoji"));
    reaction_notifications.received_reactions([
        {
            op: "remove",
            message_id: stream_message_1.id,
            user_id: jill.user_id,
            reaction_type: "unicode_emoji",
            emoji_name: "bogus",
            emoji_code: "not-a-codepoint",
        },
    ]);

    // Removing one reaction keeps the notification (reactions from other
    // users and other emoji survive) but must NOT pop up a new
    // notification, since a removed reaction is not new activity. Here
    // jill retracts the deactivated custom emoji, but her 🎉 and the
    // reactions from alice and fred remain.
    let shown_count_before = shown_count;
    removed_reaction(deactivated_realm_emoji_reaction);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), true);
    assert.equal(n.size, 2);
    assert.equal(shown_count, shown_count_before);

    // Removing a reaction that was never notified (here a different emoji
    // from a user who did react) leaves the notification untouched.
    removed_reaction({
        message_id: stream_message_1.id,
        user_id: fred.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_thumbs_up.name,
        emoji_code: emoji_thumbs_up.emoji_code,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 2);

    // Removing a reaction for a message with no notification is a no-op.
    removed_reaction({...reaction_1, message_id: 424242});
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 2);

    // Removing the remaining reactions dismisses the notification only
    // once none are left, and no removal ever pops up a notification.
    shown_count_before = shown_count;
    removed_reaction(reaction_1);
    removed_reaction(reaction_2);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), true);
    removed_reaction(reaction_3);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(stream_message_1.id.toString()), false);
    assert.equal(n.size, 1);
    assert.equal(shown_count, shown_count_before);

    // Closing a reaction notification directly
    // through desktop_notifications (as the message-read and
    // window-focus handlers do) must also clear our per-message reaction
    // state. Otherwise a later reaction to the same message would
    // resurrect the earlier reactor.
    desktop_notifications.close_notification(stream_message_2.id);
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 0);

    reaction_notifications.process_notification({
        message: stream_message_2,
        reaction_event: {
            message_id: stream_message_2.id,
            user_id: fred.user_id,
            reaction_type: "unicode_emoji",
            emoji_name: emoji_heart.name,
            emoji_code: emoji_heart.emoji_code,
        },
        desktop_notify: true,
    });
    assert.equal(
        last_shown_title,
        "translated: Fred Flintstone reacted with " + String.fromCodePoint(0x2764),
    );

    // Remove notifications.
    desktop_notifications.close_notification(stream_message_2.id);
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, stream_message_2.id.toString());
});

test("received_reactions gating", ({override}) => {
    // Reaction events are delivered to everyone who can see the message.
    // received_reactions must therefore run the message-independent checks
    // before fetching an uncached message from the server, so we don't
    // make a request for essentially every reaction in a busy channel.
    let get_called = false;
    override(channel, "get", () => {
        get_called = true;
    });
    override(user_settings, "enable_reaction_desktop_notifications", true);
    override(user_settings, "enable_reaction_audible_notifications", true);

    // Not in the message cache, so the notifiable case below fetches it.
    const uncached_message_id = 987654;
    const reaction_event = {
        message_id: uncached_message_id,
        message_sender_id: current_user.user_id,
        user_id: 2,
        reaction_type: "unicode_emoji",
        emoji_name: "tada",
        emoji_code: "1f389",
    };

    // Baseline: an unfocused user with reaction notifications enabled
    // fetches their own uncached message so it can build a notification.
    received_reaction(reaction_event);
    assert.ok(get_called);

    // A reaction by the current user is dropped without a fetch.
    get_called = false;
    received_reaction({
        ...reaction_event,
        user_id: current_user.user_id,
    });
    assert.ok(!get_called);

    // A reaction to someone else's message can never notify, and the
    // event says whose message it is, so it is dropped without a fetch.
    // This is what keeps reactions in a busy organization from costing a
    // request each.
    get_called = false;
    received_reaction({
        ...reaction_event,
        message_sender_id: 2,
    });
    assert.ok(!get_called);

    // While Zulip is focused the reaction is visible live, so it is
    // dropped without a fetch.
    override(unread_ops, "is_window_focused", () => true);
    get_called = false;
    received_reaction(reaction_event);
    assert.ok(!get_called);

    // With both reaction notification settings disabled, nothing is fetched.
    override(unread_ops, "is_window_focused", () => false);
    override(user_settings, "enable_reaction_desktop_notifications", false);
    override(user_settings, "enable_reaction_audible_notifications", false);
    get_called = false;
    received_reaction(reaction_event);
    assert.ok(!get_called);

    // With only the desktop setting on, a fetch happens only once the
    // browser notification permission has actually been granted; otherwise
    // no notification could ever result, so we skip the request. Permission
    // is read from NotificationAPI.permission.
    override(user_settings, "enable_reaction_desktop_notifications", true);
    desktop_notifications.set_notification_api({permission: "denied"});
    get_called = false;
    received_reaction(reaction_event);
    assert.ok(!get_called);

    desktop_notifications.set_notification_api({permission: "granted"});
    get_called = false;
    received_reaction(reaction_event);
    assert.ok(get_called);
});

test("received_reactions dispatches notifiable reactions", ({override}) => {
    // Drive received_reactions end to end against the real message store: it
    // should show a notification for a reaction on the current user's
    // message, ignore reactions on other people's messages, and handle the
    // cached path, the server-fetch success path, and the fetch-error path.
    let last_title = null;
    class ReactionNotification {
        static permission = "granted";

        constructor(title, {tag}) {
            this.tag = tag;
            last_title = title;
        }

        addEventListener() {}

        close() {}
    }
    desktop_notifications.set_notification_api(ReactionNotification);

    // get_notification_content parses message HTML through jQuery, which the
    // node test environment stubs.
    const $emoji_stub = $.create("reaction-emoji-stub");
    $emoji_stub.set_matches("img", false);
    $emoji_stub.set_contents([]);
    const $katex_stub = $.set_results("reaction-katex-stub", []);
    $("<div>").set_find_results(".emoji", $emoji_stub);
    $("<div>").set_find_results("span.katex", $katex_stub);
    $("<div>").set_children([]);

    people.initialize_current_user(current_user.user_id);
    const reactor = {email: "reactor@zulip.com", user_id: 99, full_name: "Reactor"};
    people.add_active_user(reactor);

    override(user_settings, "enable_reaction_desktop_notifications", true);
    override(user_settings, "enable_reaction_audible_notifications", false);

    function raw_message(id, sender_id) {
        return {
            avatar_url: "https://example.com/avatar.png",
            client: "website",
            content: "<p>a message</p>",
            content_type: "text/html",
            display_recipient: general.name,
            id,
            is_me_message: false,
            reactions: [],
            sender_email: "sender@zulip.com",
            sender_full_name: "Sender",
            sender_id,
            submessages: [],
            timestamp: 1000,
            flags: [],
            type: "stream",
            stream_id: general.stream_id,
            topic: "whatever",
            topic_links: [],
        };
    }

    function reaction_to(message_id, message_sender_id = current_user.user_id) {
        return {
            message_id,
            message_sender_id,
            user_id: reactor.user_id,
            reaction_type: "unicode_emoji",
            emoji_name: "tada",
            emoji_code: "1f389",
        };
    }

    let fetch_count = 0;
    let fetch_response;
    override(channel, "get", (opts) => {
        fetch_count += 1;
        if (fetch_response === undefined) {
            opts.error();
        } else {
            opts.success(fetch_response);
        }
    });

    // Uncached reaction to my message → fetched, processed, notification shown.
    fetch_response = {messages: [raw_message(830, current_user.user_id)]};
    received_reaction(reaction_to(830));
    let n = desktop_notifications.get_notifications();
    assert.equal(n.has("830"), true);
    assert.equal(last_title, "translated: Reactor reacted with 🎉");

    // The fetch cached the message, so a second reaction takes the cached
    // path (no fetch) and still notifies.
    last_title = null;
    received_reaction(reaction_to(830));
    assert.equal(last_title, "translated: Reactor reacted with 🎉");
    desktop_notifications.close_notification(830);

    // Reaction to a message not sent by the current user → not notifiable,
    // and rejected from the event alone, without requesting the message.
    fetch_count = 0;
    received_reaction(reaction_to(840, reactor.user_id));
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("840"), false);
    assert.equal(fetch_count, 0);

    // A failed fetch is handled without showing a notification.
    fetch_response = undefined;
    received_reaction(reaction_to(850));
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 0);

    // Retracting a reaction while its message fetch is in flight must
    // not notify once the fetch lands. Nothing would dismiss such a
    // notification: no reaction remains for a later removal to clear.
    let pending_fetch;
    override(channel, "get", (opts) => {
        pending_fetch = opts;
    });

    received_reaction(reaction_to(860));
    removed_reaction(reaction_to(860));
    last_title = null;
    pending_fetch.success({messages: [raw_message(860, current_user.user_id)]});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("860"), false);
    assert.equal(last_title, null);

    // The fetch still cached the message, so a fresh reaction to it
    // notifies without another fetch.
    pending_fetch = null;
    received_reaction(reaction_to(860));
    assert.equal(pending_fetch, null);
    assert.equal(last_title, "translated: Reactor reacted with 🎉");
    desktop_notifications.close_notification(860);

    // A reaction retracted mid-fetch only cancels itself; a different
    // reactor's reaction on the same message still notifies.
    const other_reactor = {email: "other@zulip.com", user_id: 98, full_name: "Other"};
    people.add_active_user(other_reactor);
    received_reaction(reaction_to(870));
    const first_fetch = pending_fetch;
    received_reaction({...reaction_to(870), user_id: other_reactor.user_id});
    const second_fetch = pending_fetch;

    removed_reaction(reaction_to(870));
    last_title = null;
    first_fetch.success({messages: [raw_message(870, current_user.user_id)]});
    assert.equal(last_title, null);

    second_fetch.success({messages: [raw_message(870, current_user.user_id)]});
    assert.equal(last_title, "translated: Other reacted with 🎉");
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("870"), true);
    desktop_notifications.close_notification(870);

    // A failed fetch clears its pending entry, so a later reaction from
    // the same user on the same message is not mistaken for it.
    received_reaction(reaction_to(880));
    pending_fetch.error();
    last_title = null;
    received_reaction(reaction_to(880));
    pending_fetch.success({messages: [raw_message(880, current_user.user_id)]});
    assert.equal(last_title, "translated: Reactor reacted with 🎉");
    desktop_notifications.close_notification(880);
});

test("reaction notification body", ({override}) => {
    // The reacted-to message is always the current user's own, so the body
    // must never render a direct message as "New direct message from
    // <the current user>", the way message notifications do for an
    // incoming DM.
    let last_body = null;
    class ReactionNotification {
        static permission = "granted";

        constructor(_title, {body}) {
            last_body = body;
        }

        addEventListener() {}

        close() {}
    }
    desktop_notifications.set_notification_api(ReactionNotification);

    // The body is built by parsing message HTML through jQuery, which the
    // node test environment stubs.
    const $emoji_stub = $.create("body-emoji-stub");
    $emoji_stub.set_matches("img", false);
    $emoji_stub.set_contents([]);
    const $katex_stub = $.set_results("body-katex-stub", []);
    $("<div>").set_find_results(".emoji", $emoji_stub);
    $("<div>").set_find_results("span.katex", $katex_stub);
    $("<div>").set_children([]);

    const reactor = {email: "reactor2@zulip.com", user_id: 97, full_name: "Reactor Two"};
    if (!people.is_known_user_id(reactor.user_id)) {
        people.add_active_user(reactor);
    }

    override(user_settings, "enable_reaction_desktop_notifications", true);
    override(user_settings, "enable_reaction_audible_notifications", false);

    const my_direct_message = {
        id: 3100,
        content: "<p>my secret plans</p>",
        avatar_url: "url",
        sent_by_me: true,
        sender_id: current_user.user_id,
        sender_full_name: "Me Myself",
        type: "private",
        to_user_ids: `${reactor.user_id}`,
    };

    const my_stream_message = {
        id: 3200,
        content: "<p>my channel message</p>",
        avatar_url: "url",
        sent_by_me: true,
        sender_id: current_user.user_id,
        sender_full_name: "Me Myself",
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
    };

    function reaction_to(message) {
        return {
            message_id: message.id,
            message_sender_id: current_user.user_id,
            user_id: reactor.user_id,
            reaction_type: "unicode_emoji",
            emoji_name: "tada",
            emoji_code: "1f389",
        };
    }

    function notify_about(message, plain_text_content) {
        // The body is read out of the parsed-HTML container, which zjquery
        // stubs; seed the text that container will report.
        $("<div>").text(plain_text_content);
        last_body = null;
        reaction_notifications.process_notification({
            message,
            reaction_event: reaction_to(message),
            desktop_notify: true,
        });
        desktop_notifications.close_notification(message.id);
        return last_body;
    }

    // With DM content allowed in notifications, the body is the content of
    // the user's own message, so they can tell which one was reacted to.
    override(user_settings, "pm_content_in_desktop_notifications", true);
    assert.equal(notify_about(my_direct_message, "my secret plans"), "my secret plans");

    // With DM content suppressed, the body is omitted entirely. The title
    // already names the reacting user, and the message is the current
    // user's own, so there is nothing left to say; in particular we must
    // not fall back to "New direct message from <the current user>".
    override(user_settings, "pm_content_in_desktop_notifications", false);
    assert.equal(notify_about(my_direct_message, "my secret plans"), "");

    // The setting covers direct messages only, so a reaction to the
    // user's own channel message still shows its content.
    assert.equal(notify_about(my_stream_message, "my channel message"), "my channel message");
});

test("received_reactions fetches a batch of messages at once", ({override}) => {
    // A batch of events -- what a client that has been idle receives when
    // it reconnects, which is exactly when reactions notify -- must cost
    // one request for all the messages it needs, not one per reaction.
    let last_title = null;
    class ReactionNotification {
        static permission = "granted";

        constructor(title, {tag}) {
            this.tag = tag;
            last_title = title;
        }

        addEventListener() {}

        close() {}
    }
    desktop_notifications.set_notification_api(ReactionNotification);

    // get_notification_content parses message HTML through jQuery, which the
    // node test environment stubs.
    const $emoji_stub = $.create("reaction-emoji-stub");
    $emoji_stub.set_matches("img", false);
    $emoji_stub.set_contents([]);
    const $katex_stub = $.set_results("reaction-katex-stub", []);
    $("<div>").set_find_results(".emoji", $emoji_stub);
    $("<div>").set_find_results("span.katex", $katex_stub);
    $("<div>").set_children([]);

    people.initialize_current_user(current_user.user_id);
    const reactor = {email: "batch-reactor@zulip.com", user_id: 97, full_name: "Reactor"};
    const other_reactor = {email: "batch-other@zulip.com", user_id: 96, full_name: "Other"};
    people.add_active_user(reactor);
    people.add_active_user(other_reactor);

    override(user_settings, "enable_reaction_desktop_notifications", true);
    override(user_settings, "enable_reaction_audible_notifications", false);

    function raw_message(id) {
        return {
            avatar_url: "https://example.com/avatar.png",
            client: "website",
            content: "<p>a message</p>",
            content_type: "text/html",
            display_recipient: general.name,
            id,
            is_me_message: false,
            reactions: [],
            sender_email: "sender@zulip.com",
            sender_full_name: "Sender",
            sender_id: current_user.user_id,
            submessages: [],
            timestamp: 1000,
            flags: [],
            type: "stream",
            stream_id: general.stream_id,
            topic: "whatever",
            topic_links: [],
        };
    }

    function reaction_to(message_id, op = "add", user_id = reactor.user_id) {
        return {
            op,
            message_id,
            message_sender_id: current_user.user_id,
            user_id,
            reaction_type: "unicode_emoji",
            emoji_name: "tada",
            emoji_code: "1f389",
        };
    }

    let fetches = [];
    override(channel, "get", (opts) => {
        fetches.push(opts);
    });

    // Two reactions to one uncached message and one to another, plus a
    // reaction to someone else's message and one we already have cached:
    // a single request, for just the two messages we need.
    const cached_message_id = 1830;
    message_helper.process_new_server_message(raw_message(cached_message_id));
    reaction_notifications.received_reactions([
        reaction_to(1810),
        reaction_to(1820, "add", other_reactor.user_id),
        reaction_to(1810, "add", other_reactor.user_id),
        {...reaction_to(1840), message_sender_id: reactor.user_id},
        reaction_to(cached_message_id),
    ]);
    assert.equal(fetches.length, 1);
    assert.deepEqual(JSON.parse(fetches[0].data.message_ids), [1810, 1820]);

    // The cached message notified without waiting for the request.
    let n = desktop_notifications.get_notifications();
    assert.equal(n.has(cached_message_id.toString()), true);

    fetches[0].success({messages: [raw_message(1810), raw_message(1820)]});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("1810"), true);
    assert.equal(n.has("1820"), true);
    assert.equal(n.has("1840"), false);
    // Both of the batch's reactions to 1810 are credited in its
    // notification.
    desktop_notifications.close_notification(1820);
    reaction_notifications.received_reactions([reaction_to(1810, "add", other_reactor.user_id)]);
    assert.equal(last_title, "translated: Other and Reactor reacted with 🎉");
    desktop_notifications.close_notification(1810);
    desktop_notifications.close_notification(cached_message_id);

    // A message that is gone by the time the request runs -- deleted, say
    // -- is simply absent from the response, and is not notified about.
    // Its reactions are no longer pending, so a later reaction to it is
    // fetched afresh rather than being mistaken for one of them.
    fetches = [];
    reaction_notifications.received_reactions([reaction_to(1850)]);
    fetches[0].success({messages: []});
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 0);

    reaction_notifications.received_reactions([reaction_to(1850)]);
    assert.equal(fetches.length, 2);
    fetches[1].success({messages: [raw_message(1850)]});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("1850"), true);
    desktop_notifications.close_notification(1850);

    // A reaction retracted by a later event in the same batch leaves
    // nothing to notify about, so its message is not requested at all.
    fetches = [];
    reaction_notifications.received_reactions([reaction_to(1860), reaction_to(1860, "remove")]);
    assert.equal(fetches.length, 0);

    // The rest of the batch is still fetched, and only the surviving
    // reaction notifies.
    reaction_notifications.received_reactions([
        reaction_to(1870),
        reaction_to(1870, "add", other_reactor.user_id),
        reaction_to(1870, "remove", other_reactor.user_id),
    ]);
    assert.equal(fetches.length, 1);
    assert.deepEqual(JSON.parse(fetches[0].data.message_ids), [1870]);
    last_title = null;
    fetches[0].success({messages: [raw_message(1870)]});
    assert.equal(last_title, "translated: Reactor reacted with 🎉");
    desktop_notifications.close_notification(1870);

    // A failed request clears the whole batch's pending state, so later
    // reactions to those messages are fetched again.
    fetches = [];
    reaction_notifications.received_reactions([reaction_to(1880), reaction_to(1890)]);
    fetches[0].error();
    n = desktop_notifications.get_notifications();
    assert.equal(n.size, 0);

    reaction_notifications.received_reactions([reaction_to(1880)]);
    assert.equal(fetches.length, 2);
    last_title = null;
    fetches[1].success({messages: [raw_message(1880)]});
    assert.equal(last_title, "translated: Reactor reacted with 🎉");
    desktop_notifications.close_notification(1880);
});
