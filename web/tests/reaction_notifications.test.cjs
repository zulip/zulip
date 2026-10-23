"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {$} = require("./lib/zjquery.cjs");

mock_esm("../src/electron_bridge");
mock_esm("../src/spoilers", {hide_spoilers_in_notification() {}});
const settings_data = mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});
const message_viewport = mock_esm("../src/message_viewport", {
    // The default for these tests is a user who is not watching the message
    // feed, and so has not already seen the reaction arrive.
    viewport_is_visible_and_focused: () => false,
    // Nor is the message one they can see.
    is_message_visible: () => false,
    // Composed from the two above, as the real one is, so that tests can
    // set focus and scroll position separately.
    is_message_on_screen: (message) =>
        message_viewport.viewport_is_visible_and_focused() &&
        message_viewport.is_message_visible(message.id, false),
});
// Applying a reaction to its message belongs to reaction_events' own
// tests; these are about what happens once it is applied.
mock_esm("../src/emoji_frequency", {
    update_emoji_frequency_on_add_reaction_event() {},
    update_emoji_frequency_on_remove_reaction_event() {},
});
mock_esm("../src/message_events", {
    update_views_filtered_on_message_property() {},
});

const message_view = mock_esm("../src/message_view", {
    narrow_to_message_near() {},
});

const desktop_notifications = zrequire("desktop_notifications");
const message_helper = zrequire("message_helper");
const message_store = zrequire("message_store");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const reaction_events = zrequire("reaction_events");
const reaction_notifications = zrequire("reaction_notifications");
const reactions = zrequire("reactions");
const stream_data = zrequire("stream_data");
const user_topics = zrequire("user_topics");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

set_realm({});
const current_user = {user_id: 1};
set_current_user(current_user);
people.initialize_current_user(current_user.user_id);
const user_settings = {};
initialize_user_settings({user_settings});

const me = make_user({user_id: current_user.user_id, full_name: "Me Myself"});
const alice = make_user({user_id: 2, full_name: "Alice"});
const bob = make_user({user_id: 3, full_name: "Bob"});
const cindy = make_user({user_id: 4, full_name: "Cindy"});
const muted_reactor = make_user({user_id: 5, full_name: "Muted"});
for (const user of [me, alice, bob, cindy, muted_reactor]) {
    people.add_active_user(user);
}

// A user this client has no record of, as happens in a realm where users
// cannot access all other users.
const inaccessible_user_id = 99;

const general = make_stream({name: "general", stream_id: 10, is_muted: false});
const muted = make_stream({name: "muted", stream_id: 20, is_muted: true});
stream_data.add_sub_for_tests(general);
stream_data.add_sub_for_tests(muted);

for (const [stream, topic, visibility_policy] of [
    [general, "muted topic", user_topics.all_visibility_policies.MUTED],
    [muted, "unmuted topic", user_topics.all_visibility_policies.UNMUTED],
    [muted, "followed topic", user_topics.all_visibility_policies.FOLLOWED],
]) {
    user_topics.update_user_topics(stream.stream_id, stream.name, topic, visibility_policy);
}

// The stubbed notification API of the current test.
let notices;

function test(label, f) {
    run_test(label, (helpers) => {
        // The cached messages and live notifications a test makes are its
        // own; the next test starts with none of them.
        notices = stub_notification_api();
        stub_message_content_parsing();
        message_store.clear_for_testing();
        desktop_notifications.notice_memory.clear();
        muted_users.set_muted_users([]);
        helpers.override_rewire(reactions, "add_reaction", noop, {unused: false});
        helpers.override_rewire(reactions, "remove_reaction", noop, {unused: false});
        helpers.override(user_settings, "enable_reaction_desktop_notifications", true);
        helpers.override(user_settings, "enable_reaction_audible_notifications", false);
        helpers.override(user_settings, "notification_sound", "ding");
        helpers.override(user_settings, "emojiset", "google");
        f(helpers);
    });
}

const tada = {reaction_type: "unicode_emoji", emoji_name: "tada", emoji_code: "1f389"};
const thumbs_up = {reaction_type: "unicode_emoji", emoji_name: "thumbs_up", emoji_code: "1f44d"};
const realm_tada = {reaction_type: "realm_emoji", emoji_name: "tada", emoji_code: "5"};
// A realm emoji that took over the name of the one above, as happens when a
// custom emoji is deactivated and a new one is uploaded with the same name.
const newer_realm_tada = {reaction_type: "realm_emoji", emoji_name: "tada", emoji_code: "9"};
// A deactivated custom emoji, whose name is absent from `emoji.emojis_by_name`
// but which can still receive new votes.
const deactivated_realm_emoji = {
    reaction_type: "realm_emoji",
    emoji_name: "deactivated_custom",
    emoji_code: "1234",
};
const invalid_unicode_emoji = {
    reaction_type: "unicode_emoji",
    emoji_name: "bogus",
    emoji_code: "not-a-codepoint",
};

function reaction_event(message_id, user_id, emoji = tada) {
    // Every reaction here is to one of the current user's own messages, which
    // is what makes it a candidate for a notification at all.
    return {message_id, message_sender_id: current_user.user_id, user_id, ...emoji};
}

function added(event) {
    return {...event, op: "add"};
}

function retracted(event) {
    return {...event, op: "remove"};
}

function received_reaction(event) {
    reaction_events.received_reactions([added(event)]);
}

function removed_reaction(event) {
    reaction_events.received_reactions([retracted(event)]);
}

function stub_notification_api(permission = "granted") {
    const notices = {
        last_title: undefined,
        last_body: undefined,
        last_icon: undefined,
        last_tag: undefined,
        title_by_tag: new Map(),
        closed_tags: [],
        // Counts how many notifications have been shown, so tests can verify
        // that an operation does (or does not) pop one up.
        shown_count: 0,
        close_handlers: new Map(),
        click_handlers_by_tag: new Map(),
    };

    class StubNotification {
        static permission = permission;

        constructor(title, {icon, body, tag}) {
            this.tag = tag;
            notices.last_title = title;
            notices.last_body = body;
            notices.last_icon = icon;
            notices.last_tag = tag;
            notices.title_by_tag.set(tag, title);
            notices.shown_count += 1;
        }

        addEventListener(type, handler) {
            if (type === "close") {
                notices.close_handlers.set(this, handler);
            } else if (type === "click") {
                notices.click_handlers_by_tag.set(this.tag, handler);
            }
        }

        close() {
            notices.closed_tags.push(this.tag);
            // Dispatch the close event before returning, as an implementation
            // whose close() is not asynchronous does.
            notices.close_handlers.get(this)();
        }
    }

    desktop_notifications.set_notification_api(StubNotification);
    return notices;
}

function viewport_showing(...visible_message_ids) {
    // Stands in for the feed being scrolled so that exactly these messages
    // are on screen.
    const visible = new Set(visible_message_ids);
    return (message_id) => visible.has(message_id);
}

function stub_message_content_parsing() {
    // The notification body is built by parsing message HTML through jQuery,
    // which the node test environment stubs.
    const $emoji_stub = $.create("emoji-stub");
    $emoji_stub.set_matches("img", false);
    $emoji_stub.set_contents([]);
    const $katex_stub = $.set_results("katex-stub", []);
    $("<div>").set_find_results(".emoji", $emoji_stub);
    $("<div>").set_find_results("span.katex", $katex_stub);
    $("<div>").set_children([]);
}

function my_channel_message(id) {
    return {
        id,
        type: "stream",
        content: "<p>my channel message</p>",
        stream_id: general.stream_id,
        topic: "whatever",
    };
}

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
        sender_email: me.email,
        sender_full_name: me.full_name,
        sender_id: current_user.user_id,
        submessages: [],
        timestamp: 1000,
        flags: ["read"],
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
        topic_links: [],
    };
}

function cache_message(id) {
    message_helper.process_new_server_message(raw_message(id));
}

function count_sounds(override) {
    override(user_settings, "enable_reaction_audible_notifications", true);
    const sounds = {played: 0};
    $("#user-notification-sound-audio")[0].play = async () => {
        sounds.played += 1;
    };
    return sounds;
}

function react(message, user_id, emoji = tada) {
    reaction_notifications.process_notification({
        message,
        reaction_events: [reaction_event(message.id, user_id, emoji)],
    });
}

test("reaction_is_notifiable honors muted channels and topics", () => {
    const cases = [
        // A reaction to a message in a muted channel does not notify, unless
        // the topic overrides the channel's visibility.
        {stream: muted, topic: "a topic that inherits visibility", notifiable: false},
        {stream: muted, topic: "unmuted topic", notifiable: true},
        {stream: muted, topic: "followed topic", notifiable: true},
        // Nor does one to a muted topic in a channel that is not muted.
        {stream: general, topic: "muted topic", notifiable: false},
        {stream: general, topic: "whatever", notifiable: true},
    ];

    for (const [i, {stream, topic, notifiable}] of cases.entries()) {
        const message = {id: i, type: "stream", stream_id: stream.stream_id, topic};
        assert.equal(
            reaction_notifications.reaction_is_notifiable(message),
            notifiable,
            `${stream.name} > ${topic}`,
        );
    }

    // A direct message has no channel or topic to mute.
    assert.ok(reaction_notifications.reaction_is_notifiable({id: 100, type: "private"}));
});

test("reactions that cannot notify are dropped", () => {
    const message_id = 3000;
    cache_message(message_id);

    function notifies(event) {
        notices.shown_count = 0;
        received_reaction(event);
        desktop_notifications.close_notification(message_id);
        return notices.shown_count === 1;
    }

    // Baseline: another user's reaction to the current user's message.
    const event = reaction_event(message_id, alice.user_id);
    assert.ok(notifies(event));

    // A reaction by the current user does not notify.
    assert.ok(!notifies({...event, user_id: current_user.user_id}));

    // Nor does a reaction to someone else's message, which the event
    // identifies by its sender.
    assert.ok(!notifies({...event, message_sender_id: alice.user_id}));

    // Nor does a reaction from a muted user.
    muted_users.add_muted_user(muted_reactor.user_id);
    assert.ok(!notifies({...event, user_id: muted_reactor.user_id}));
});

test("reaction notification titles", ({override}) => {
    // The title credits the newest reactor first, and counts the rest.
    const message = my_channel_message(3300);
    react(message, alice.user_id);
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");
    react(message, bob.user_id);
    assert.equal(notices.last_title, "translated: Bob and Alice reacted with 🎉");
    react(message, cindy.user_id);
    assert.equal(notices.last_title, "translated: Cindy and 2 others reacted with 🎉");

    // Unicode emoji render as the glyph; realm emoji as `:emoji_name:`, so a
    // realm emoji named after a Unicode one is listed separately.
    const other_message = my_channel_message(3310);
    react(other_message, alice.user_id);
    react(other_message, bob.user_id, realm_tada);
    assert.equal(notices.last_title, "translated: Bob and Alice reacted with :tada:, 🎉");

    // A newer realm emoji that reused the name renders the same way, so it
    // does not add a second `:tada:` to the title.
    react(other_message, alice.user_id, newer_realm_tada);
    assert.equal(notices.last_title, "translated: Alice and Bob reacted with :tada:, 🎉");

    // A reaction with a realm emoji that is no longer active is still
    // rendered from the event's own fields.
    react(other_message, bob.user_id, deactivated_realm_emoji);
    assert.ok(notices.last_title.includes(":deactivated_custom:"));

    // An emoji_code that is not a valid codepoint is logged, and falls back
    // to `:emoji_name:`.
    blueslip.expect("error", "Invalid unicode codepoint for emoji");
    react(other_message, bob.user_id, invalid_unicode_emoji);
    assert.ok(notices.last_title.includes(":bogus:"));
    // In particular, the unrenderable emoji_code is not shown raw.
    assert.ok(!notices.last_title.includes("not-a-codepoint"));

    // The text emojiset shows even Unicode emoji as `:emoji_name:`.
    override(user_settings, "emojiset", "text");
    const text_emojiset_message = my_channel_message(3320);
    react(text_emojiset_message, alice.user_id);
    assert.equal(notices.last_title, "translated: Alice reacted with :tada:");
});

test("reactions to one message share a notification", () => {
    const message = my_channel_message(3300);
    const other_message = my_channel_message(3400);

    react(message, alice.user_id);
    const notifications = desktop_notifications.get_notifications();
    assert.equal(notifications.size, 1);
    assert.ok(notifications.has(message.id.toString()));
    assert.equal(notices.last_tag, message.id.toString());

    // Further reactions to the same message update that one notification,
    // rather than stacking up.
    const superseded_notification = notifications.get(message.id.toString()).obj;
    react(message, bob.user_id);
    react(message, bob.user_id, thumbs_up);
    assert.equal(desktop_notifications.get_notifications().size, 1);

    // A reaction to another message gets a notification of its own.
    react(other_message, alice.user_id);
    assert.equal(desktop_notifications.get_notifications().size, 2);

    // The superseded notification's close event, arriving late, must not
    // discard the reactions stored with its replacement.
    notices.close_handlers.get(superseded_notification)();
    assert.equal(desktop_notifications.get_notifications().size, 2);
    react(message, cindy.user_id);
    assert.equal(notices.last_title, "translated: Cindy and 2 others reacted with 🎉, 👍");

    // Closing the notification discards its reactions, so a later reaction
    // starts afresh.
    desktop_notifications.close_notification(message.id);
    assert.equal(desktop_notifications.get_notifications().size, 1);
    react(message, bob.user_id);
    assert.equal(notices.last_title, "translated: Bob reacted with 🎉");
});

test("removing a reaction updates or dismisses its notification", () => {
    const message = my_channel_message(3300);
    react(message, alice.user_id);
    react(message, bob.user_id);
    react(message, bob.user_id, thumbs_up);

    // Removing one reaction keeps the notification, without popping it up
    // again, since a removal is not new activity.
    notices.shown_count = 0;
    removed_reaction(reaction_event(message.id, bob.user_id, thumbs_up));
    assert.ok(desktop_notifications.get_notifications().has(message.id.toString()));
    assert.equal(notices.shown_count, 0);

    // Its title still credits the removed reaction, since changing the title
    // would pop the notification up again.
    assert.equal(notices.last_title, "translated: Bob and Alice reacted with \u{1F44D}, \u{1F389}");

    // Removing a reaction that was never notified about leaves the
    // notification untouched.
    removed_reaction(reaction_event(message.id, cindy.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 1);

    // Removing a reaction for a message with no notification is a no-op.
    removed_reaction(reaction_event(424_242, alice.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 1);

    // Once Bob's last reaction is removed, the next reaction rebuilds the
    // notification without crediting him or his emoji.
    removed_reaction(reaction_event(message.id, bob.user_id));
    assert.ok(desktop_notifications.get_notifications().has(message.id.toString()));
    assert.equal(notices.shown_count, 0);
    react(message, cindy.user_id);
    assert.equal(notices.shown_count, 1);
    assert.equal(notices.last_title, "translated: Cindy and Alice reacted with \u{1F389}");

    // The notification is dismissed only once no notified reaction remains.
    notices.shown_count = 0;
    notices.closed_tags.length = 0;
    removed_reaction(reaction_event(message.id, alice.user_id));
    assert.ok(desktop_notifications.get_notifications().has(message.id.toString()));
    assert.deepEqual(notices.closed_tags, []);
    removed_reaction(reaction_event(message.id, cindy.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 0);
    assert.deepEqual(notices.closed_tags, [message.id.toString()]);
    assert.equal(notices.shown_count, 0);
});

test("a removal dismisses its notification even when notifications are off", ({override}) => {
    // Otherwise a notification shown before the user turned notifications
    // off could never be dismissed.
    const message = my_channel_message(3500);
    react(message, alice.user_id);
    assert.ok(desktop_notifications.get_notifications().has(message.id.toString()));

    override(user_settings, "enable_reaction_desktop_notifications", false);
    override(user_settings, "enable_reaction_audible_notifications", false);

    notices.closed_tags.length = 0;
    removed_reaction(reaction_event(message.id, alice.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 0);
    assert.deepEqual(notices.closed_tags, [message.id.toString()]);
});

test("reactions notify unless the message is on screen", ({override}) => {
    const message_id = 3700;
    cache_message(message_id);

    function reactions_shown() {
        notices.shown_count = 0;
        received_reaction(reaction_event(message_id, alice.user_id));
        desktop_notifications.close_notification(message_id);
        return notices.shown_count;
    }

    // Zulip in the background, an overlay covering the feed, or a view that
    // replaces the feed entirely: viewport_is_visible_and_focused is false
    // (the default here) and the reaction notifies.
    assert.equal(reactions_shown(), 1);

    // Watching the feed, but the message is not on screen -- scrolled past,
    // or in a conversation the user is not viewing: it still notifies.
    override(message_viewport, "viewport_is_visible_and_focused", () => true);
    assert.equal(reactions_shown(), 1);

    // The message is on screen: the reaction appears in front of the user,
    // so we stay quiet.
    override(message_viewport, "is_message_visible", viewport_showing(message_id));
    assert.equal(reactions_shown(), 0);
});

test("reaction notification body", ({override}) => {
    // The reacted-to message is always the current user's own.

    const my_direct_message = {id: 3100, type: "private", content: "<p>my secret plans</p>"};
    const my_stream_message = my_channel_message(3200);

    function notify_about(message, plain_text_content) {
        // The body is read out of the parsed-HTML container, which zjquery
        // stubs; seed the text that container will report.
        $("<div>").text(plain_text_content);
        notices.last_body = undefined;
        react(message, alice.user_id);
        return notices.last_body;
    }

    // With DM content allowed in notifications, the body is the content of the
    // user's own message, so they can tell which one was reacted to.
    override(user_settings, "pm_content_in_desktop_notifications", true);
    assert.equal(notify_about(my_direct_message, "my secret plans"), "my secret plans");

    // With DM content suppressed, the body says only that there was a
    // reaction.
    override(user_settings, "pm_content_in_desktop_notifications", false);
    assert.equal(
        notify_about(my_direct_message, "my secret plans"),
        "translated: New reaction to your direct message.",
    );

    // The setting covers direct messages only, so a reaction to the user's own
    // channel message still shows its content.
    assert.equal(notify_about(my_stream_message, "my channel message"), "my channel message");
});

test("reaction notification from an inaccessible user", ({override}) => {
    // A reactor this client cannot access is credited as "Unknown user", as
    // in the message feed.
    override(settings_data, "user_can_access_all_other_users", () => false);
    assert.ok(!people.is_known_user_id(inaccessible_user_id));

    const message_id = 1900;
    cache_message(message_id);
    received_reaction(reaction_event(message_id, inaccessible_user_id));

    assert.ok(desktop_notifications.get_notifications().has(message_id.toString()));
    assert.equal(notices.last_title, "translated: translated: Unknown user reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${inaccessible_user_id}`);
});

test("a reaction retracted in the same batch does not notify", () => {
    // Reacting and then unreacting while the user is away is not worth a
    // notification.
    const message_id = 3600;
    cache_message(message_id);

    // The retraction that follows the add drops it, so nothing is shown.
    reaction_events.received_reactions([
        added(reaction_event(message_id, alice.user_id)),
        retracted(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(notices.shown_count, 0);
    assert.equal(desktop_notifications.get_notifications().size, 0);

    // A retraction *before* the add is the opposite sequence: the user reacted
    // again, which is new activity and does notify.
    reaction_events.received_reactions([
        retracted(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(notices.shown_count, 1);
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");

    // Retracting a different reaction leaves the added one to notify, and the
    // title credits only the reaction that survived the batch.
    notices.shown_count = 0;
    reaction_events.received_reactions([
        added(reaction_event(message_id, alice.user_id, thumbs_up)),
        retracted(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(notices.shown_count, 1);
    assert.equal(notices.last_title, "translated: Alice reacted with 👍");
});

test("a reaction re-added within one batch is credited as the newest", () => {
    // Setting a key a Map already has leaves it in its original position, so
    // a re-added reaction has to be deleted first to sort as the newest.
    const message_id = 3800;
    cache_message(message_id);

    reaction_events.received_reactions([
        added(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, bob.user_id)),
        retracted(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, alice.user_id)),
    ]);

    assert.equal(notices.last_title, "translated: Alice and Bob reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${alice.user_id}`);
    // The batch is notified about once, crediting the add of Alice's that
    // survived it, rather than once for each reaction in it.
    assert.equal(notices.shown_count, 1);

    reaction_events.received_reactions([
        retracted(reaction_event(message_id, bob.user_id)),
        added(reaction_event(message_id, bob.user_id)),
    ]);

    assert.equal(notices.last_title, "translated: Bob and Alice reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${bob.user_id}`);
});

test("reactions to a message in one batch share one notification and sound", ({override}) => {
    const sounds = count_sounds(override);
    const message_id = 4100;
    cache_message(message_id);

    reaction_events.received_reactions([
        added(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, bob.user_id)),
        added(reaction_event(message_id, cindy.user_id, thumbs_up)),
    ]);
    assert.equal(notices.shown_count, 1);
    assert.equal(sounds.played, 1);
    assert.equal(notices.last_title, "translated: Cindy and 2 others reacted with 👍, 🎉");

    // A notification that is not wanted does not stop the sound.
    override(user_settings, "enable_reaction_desktop_notifications", false);
    reaction_events.received_reactions([
        added(reaction_event(message_id, alice.user_id, thumbs_up)),
    ]);
    assert.equal(notices.shown_count, 1);
    assert.equal(sounds.played, 2);
});

test("clicking a reaction notification opens the message", ({override}) => {
    const message_id = 4200;
    cache_message(message_id);
    const message = message_store.get(message_id);
    let narrowed_to;
    override(message_view, "narrow_to_message_near", (narrowed_message, trigger) => {
        narrowed_to = narrowed_message;
        assert.equal(trigger, "notification");
    });
    override(window, "focus", noop);

    received_reaction(reaction_event(message_id, alice.user_id));
    notices.click_handlers_by_tag.get(message_id.toString())();
    assert.equal(narrowed_to, message);
});

test("one message's reactions failing does not stop the rest of the batch", () => {
    cache_message(4300);
    cache_message(4310);

    // A reactor this client does not know trips an assertion while the
    // notification is built.
    const unknown_user_id = 9999;
    blueslip.expect("error", "Failed to process reactions to a message");
    reaction_events.received_reactions([
        added(reaction_event(4300, unknown_user_id)),
        added(reaction_event(4310, alice.user_id)),
    ]);
    assert.equal(notices.title_by_tag.get("4310"), "translated: Alice reacted with 🎉");
});
