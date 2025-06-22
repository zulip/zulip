"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

mock_esm("../src/electron_bridge");
mock_esm("../src/spoilers", {hide_spoilers_in_notification() {}});

const user_topics = zrequire("user_topics");
const stream_data = zrequire("stream_data");

const desktop_notifications = zrequire("desktop_notifications");
const message_notifications = zrequire("message_notifications");
const emoji = zrequire("emoji");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");
const people = zrequire("people");
const reaction_notifications = zrequire("reaction_notifications");

const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);
const user_settings = {};
initialize_user_settings({user_settings});

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

    // Case 9: If a message is in a muted topic
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

    // Case 10:
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

    // Case 11: If `None` is selected as the notification sound, send no
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
    // Message is not sent by user and should not notify current user
    let message = {
        id: 1,
        type: "private",
        content: "React to DM",
        sender_id: "1",
        to_user_ids: "31",
        sent_by_me: false,
        locally_echoed: true,
        notification_sent: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message), false);

    message = {
        id: 2,
        content: "Someone else reacted",
        type: "stream",
        stream_id: general.stream_id,
        topic: "followed topic",
        sent_by_me: false,
        notification_sent: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message), false);

    message = {
        id: 3,
        type: "private",
        content: "React to my DM",
        sender_id: "1",
        to_user_ids: "31",
        sent_by_me: true,
        locally_echoed: true,
        notification_sent: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message), true);

    message = {
        id: 4,
        content: "React to my followed topic message",
        type: "stream",
        stream_id: general.stream_id,
        topic: "followed topic",
        sent_by_me: true,
        notification_sent: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message), true);

    message = {
        id: 5,
        content: "React to my unmuted topic message",
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
        sent_by_me: true,
        notification_sent: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message), true);

    message = {
        id: 6,
        content: "React to my muted topic message",
        type: "stream",
        stream_id: general.stream_id,
        topic: "muted topic",
        sent_by_me: true,
        notification_sent: false,
    };
    assert.equal(reaction_notifications.reaction_is_notifiable(message), false);
});

test("basic_notifications", () => {
    $("<div>").set_find_results(".emoji", {text: () => ({contents: () => ({unwrap() {}})})});
    $("<div>").set_find_results("span.katex", {each() {}});
    $("<div>").children = () => [];

    let n; // Object for storing all notification data for assertions.
    let last_closed_message_id = null;
    let last_shown_message_id = null;

    // Notifications API stub
    class StubNotification {
        constructor(_title, {icon, body, tag}) {
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

    desktop_notifications.set_notification_api(StubNotification);

    const message_1 = {
        id: 1000,
        content: "@-mentions the user",
        avatar_url: "url",
        sent_by_me: false,
        sender_full_name: "Jesse Pinkman",
        notification_sent: false,
        mentioned_me_directly: true,
        type: "stream",
        stream_id: general.stream_id,
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
        stream_id: general.stream_id,
        topic: "lunch",
    };

    // Send notification.
    message_notifications.process_notification({message: message_1, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id.toString());

    // Remove notification.
    desktop_notifications.close_notification(message_1);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, message_1.id.toString());

    // Send notification.
    message_1.id = 1001;
    message_notifications.process_notification({message: message_1, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id.toString());

    // Process same message again. Notification count shouldn't increase.
    message_1.id = 1002;
    message_notifications.process_notification({message: message_1, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id.toString());

    // Send another message. Notification count should increase.
    message_notifications.process_notification({message: message_2, desktop_notify: true});
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("Gus Fring to general > lunch"), true);
    assert.equal(n.has("Jesse Pinkman to general > whatever"), true);
    assert.equal(n.size, 2);
    assert.equal(last_shown_message_id, message_2.id.toString());

    // Remove notifications.
    desktop_notifications.close_notification(message_1);
    desktop_notifications.close_notification(message_2);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has("Jesse Pinkman to general > whatever"), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, message_2.id.toString());

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

    const name_to_codepoint = {};
    for (const [key, val] of emojis_by_name.entries()) {
        name_to_codepoint[key] = val.emoji_code;
    }

    const codepoint_to_name = {};
    for (const [key, val] of emojis_by_name.entries()) {
        codepoint_to_name[val.emoji_code] = key;
    }

    const emoji_codes = {
        name_to_codepoint,
        names: [...emojis_by_name.keys()],
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

    for (const [key, val] of emojis_by_name.entries()) {
        emoji.emojis_by_name.set(key, val);
    }

    const reaction_1 = {
        message_id: 1000,
        user_id: alice.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_tada.name,
        emoji_code: emoji_tada.emoji_code,
    };
    const reaction_2 = {
        message_id: 1000,
        user_id: jill.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_tada.name,
        emoji_code: emoji_tada.emoji_code,
    };
    const reaction_3 = {
        message_id: 1000,
        user_id: fred.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_heart.name,
        emoji_code: emoji_heart.emoji_code,
    };

    const reaction_4 = {
        message_id: 1500,
        user_id: alice.user_id,
        reaction_type: "unicode_emoji",
        emoji_name: emoji_tada.name,
        emoji_code: emoji_tada.emoji_code,
    };

    // Incoming reaction event should notify user
    reaction_notifications.process_notification({
        message: message_1,
        reaction_event: reaction_1,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(message_1.id.toString()), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id.toString());

    // Reaction to same message shouldn't increase notification obj
    reaction_notifications.process_notification({
        message: message_1,
        reaction_event: reaction_2,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(message_1.id.toString()), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id.toString());

    // Send another reaction to same message
    reaction_notifications.process_notification({
        message: message_1,
        reaction_event: reaction_3,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(message_1.id.toString()), true);
    assert.equal(n.size, 1);
    assert.equal(last_shown_message_id, message_1.id.toString());

    // Reaction to another message should increase notification obj
    reaction_notifications.process_notification({
        message: message_2,
        reaction_event: reaction_4,
        desktop_notify: true,
    });
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(message_2.id.toString()), true);
    assert.equal(n.size, 2);
    assert.equal(last_shown_message_id, message_2.id.toString());

    // Remove notifications.
    desktop_notifications.close_notification(message_1);
    desktop_notifications.close_notification(message_2);
    n = desktop_notifications.get_notifications();
    assert.equal(n.has(message_1.id.toString()), false);
    assert.equal(n.has(message_2.id.toString()), false);
    assert.equal(n.size, 0);
    assert.equal(last_closed_message_id, message_2.id.toString());
});
